"""Manual retained-model compatibility and incomplete-validation checks."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import joblib
import pandas as pd

from xenix.services.data_tokenization_contracts import TextPreparationInput, TextProcessingOptions
from xenix.services.ml.evaluation import get_default_policy
from xenix.services.ml.models.text_analysis import MultilingualTextClassifier, MultilingualTextClassificationService
from xenix.services.ml.text_classification_evaluation import read_cross_validation, write_cross_validation
from xenix.services.ml.text_preparation import build_text_preparer, prepare_text_classification_data
from xenix.services.ml.types import EvaluationKind

frame = pd.DataFrame({'message':['invoice company tax','billing receipt refund','tracking courier parcel','shipment delivery address'],
                      'label':['finance','finance','logistics','logistics'],'group':['a','a','b','b']})
preparer = build_text_preparer(TextPreparationInput())
classifier = MultilingualTextClassifier(preparer=preparer).fit(frame.message,frame.label)
before = classifier.predict(frame.message).tolist()
# Model the old pickle shape: the original preparer had no configurable strategy fields.
for name in TextProcessingOptions.model_fields:
    preparer.specification.__dict__.pop(name,None)
with TemporaryDirectory(prefix='xenix-text-compatibility-') as folder:
    path = Path(folder)
    joblib.dump(classifier,path/'legacy.joblib')
    restored = joblib.load(path/'legacy.joblib')
    assert restored.predict(frame.message).tolist()==before
    assert restored.feature_coverage(pd.Series([''])).iloc[0].prediction_evidence=='no_known_features'
    policy = get_default_policy(EvaluationKind.CLASSIFICATION,model_key=MultilingualTextClassificationService.key)
    evidence=[]
    for single_group in [False,True]:
        data=frame.assign(group='one') if single_group else frame
        prepared=prepare_text_classification_data(data,text_column='message',target_column='label',business_group_column='group',preparer=preparer)
        destination=path/f'{single_group}.pkl'
        write_cross_validation(prepared,build_estimator=lambda:MultilingualTextClassifier(preparer=preparer),
            policy=policy,source_sha256='manual-example',path=destination)
        result=read_cross_validation(destination,policy)
        assert result['cross_validation']['status']=='incomplete'
        assert 'evaluation' not in result
        evidence.append(result)
result={'old_pickle_shape_preserves_predictions':True,'incomplete_group_validation':evidence}
(Path(__file__).parent/'compatibility-probes.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=False))
