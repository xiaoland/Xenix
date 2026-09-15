"""Manual production-adapter checks; no provider calls and no benchmark oracle fitting."""
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import joblib
import numpy as np
import pandas as pd

from xenix.services.data_tokenization_contracts import TextPreparationInput, TextProcessingOptions
from xenix.services.ml.contracts import ApplyTaskRequest, EvaluateTaskRequest, FitTaskRequest
from xenix.services.ml.evaluation import get_default_policy
from xenix.services.ml.models.text_analysis import MultilingualTextClassificationParams, MultilingualTextClassificationService
from xenix.services.ml.types import EvaluationKind

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT/'tests/e2e/agent_harness/fixtures/business_tasks/routing/confirmation'
SERVICE = MultilingualTextClassificationService
results = []
with TemporaryDirectory(prefix='xenix-text-strategies-') as folder:
    work = Path(folder)
    for strategy in ['words','characters','pretokenized']:
        params = MultilingualTextClassificationParams(text_strategy=strategy)
        history = pd.read_csv(FIXTURES/'history.csv')
        incoming = pd.read_csv(FIXTURES/'new_tickets.csv')
        # Pretokenized mode exercises Agent-supplied tokens without another segmentation pass.
        if strategy == 'pretokenized':
            import jieba
            history.message = history.message.map(lambda text:' '.join(jieba.lcut(text,HMM=False)))
            incoming.message = incoming.message.map(lambda text:' '.join(jieba.lcut(text,HMM=False)))
        incoming.loc[len(incoming)] = ['probe-empty','probe','probe','']
        source = work/f'{strategy}.parquet'; history.to_parquet(source)
        apply_source = work/f'{strategy}-apply.parquet'; incoming.to_parquet(apply_source)
        common = dict(project_id=1,dataset_id=2,dataset_source_path=str(source),evaluation_kind=EvaluationKind.CLASSIFICATION,
            train_role_bindings=[{'role':'text','columns':['message']},{'role':'target','columns':['queue']},{'role':'group','columns':['customer_batch']}],
            evaluation_policy=get_default_policy(EvaluationKind.CLASSIFICATION,group_aware=True,model_key=SERVICE.key),
            dataset_snapshot={'dataset_id':2,'source_sha256':sha256(source.read_bytes()).hexdigest(),'source_byte_size':source.stat().st_size,'schema_digest':'probe'},
            text_preparation=TextPreparationInput(**{name:getattr(params,name) for name in TextProcessingOptions.model_fields}))
        fit = SERVICE.fit(FitTaskRequest(task_id=3,**common,manual_training={'model_key':SERVICE.key,'params':params.model_dump()}),work/strategy)
        evaluation = SERVICE.evaluate(EvaluateTaskRequest(task_id=4,**common,evaluate_model={'trained_model_id':5,'model_key':SERVICE.key,
            'trained_model_artifact_path':fit.model_artifact_path,'holdout_artifact_path':fit.holdout_artifact_path}),work/strategy)
        applied = SERVICE.apply(ApplyTaskRequest(task_id=6,project_id=1,dataset_id=7,dataset_source_path=str(apply_source),feature_columns=['message'],
            apply_model={'trained_model_id':5,'model_key':SERVICE.key,'trained_model_artifact_path':fit.final_model_artifact_path},
            input_files=[{'absolute_path':str(apply_source),'file_name':apply_source.name,'source_kind':'dataset','dataset_id':7}]),work/strategy)
        output = pd.read_csv(applied.output_file_path)
        estimator = joblib.load(fit.final_model_artifact_path)
        assert output.prediction.tolist() == estimator.predict(incoming.message).tolist()
        assert output.iloc[-1].prediction_evidence == 'no_known_features'
        assert evaluation.cross_validation['status']=='complete'
        folds = pd.read_pickle(fit.holdout_artifact_path)
        assert all(f['group_overlap_count']==0 for f in evaluation.cross_validation['folds'])
        assert np.mean(folds.target==folds.prediction)==evaluation.evaluation.metrics['accuracy']
        results.append({'strategy':strategy,'cv':evaluation.cross_validation,'metrics':evaluation.evaluation.metrics,
            'apply_feedback':applied.text_classification_apply_facts.feature_coverage,
            'columns':output.columns.tolist(),'predictions':output.prediction.iloc[:30].tolist()})
    # Numeric target labels must not become sklearn's unknown object target type in stored OOF records.
    from xenix.services.ml.text_classification_evaluation import read_cross_validation
    numeric = pd.read_pickle(fit.holdout_artifact_path)
    mapping = {name:index for index,name in enumerate(numeric.attrs['classes'])}
    for column in ['target','prediction','baseline']:
        numeric[column] = numeric[column].map(mapping)
    numeric.attrs['classes'] = np.arange(len(mapping))
    numeric.to_pickle(work/'numeric.pkl')
    assert read_cross_validation(work/'numeric.pkl',common['evaluation_policy'])['cross_validation']['status']=='complete'
(Path(__file__).parent/'strategy-probes.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
print([(row['strategy'],row['metrics']['accuracy']) for row in results])
