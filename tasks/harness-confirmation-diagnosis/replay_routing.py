"""Offline diagnosis of saved routing runs; no provider calls or product changes."""
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

from xenix.services.data_tokenization_contracts import TextPreparationInput
from xenix.services.ml.models.text_analysis import MultilingualTextClassifier
from xenix.services.ml.preparation import prepare_supervised_split
from xenix.services.ml.text_preparation import build_text_preparer, prepare_text_classification_data
from xenix.services.ml.types import EvaluationKind
from xenix.services.storage.models import DatasetSourceFormat
from xenix.services.tabular import load_tabular_frame

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / 'tests/e2e/agent_harness/fixtures/business_tasks/routing'
history = pd.read_csv(FOLDER / 'confirmation/history.csv')
incoming = pd.read_csv(FOLDER / 'confirmation/new_tickets.csv')
truth = json.loads((FOLDER / 'confirmation/oracle.json').read_text(encoding='utf8'))['labels']
report = json.loads(next((ROOT / 'build/agent-harness-namespace-d7bbe8d/confirmation').glob('business.routing.*.json')).read_text(encoding='utf8'))
calls = next(e['attributes']['tool_calls'] for e in report['trace']['events'] if e['name'] == 'benchmark.subject.outcome')
source_buffer = BytesIO()
load_tabular_frame(FOLDER / 'confirmation/history.csv', DatasetSourceFormat.CSV).write_parquet(source_buffer)
source_sha = sha256(source_buffer.getvalue()).hexdigest()
evidence = {'materialized_history_parquet_sha256': source_sha, 'configurations': []}

for call in calls:
    if call['name'] != 'model.train':
        continue
    saved = call['delivery']['models'][0]
    params = saved['params']
    preparer = build_text_preparer(TextPreparationInput(phrase_mode=params['phrase_mode']))
    prepared = prepare_text_classification_data(history, text_column='message', target_column='queue', business_group_column='customer_batch', preparer=preparer)
    request = SimpleNamespace(evaluation_kind=EvaluationKind.CLASSIFICATION,
        evaluation_policy=SimpleNamespace(policy_key='classification.default.v1', split_strategy='group_hash_holdout.v2', test_size=0.2, random_state=42),
        dataset_snapshot=SimpleNamespace(source_sha256=source_sha, sampling_fingerprint=source_sha))
    split = prepare_supervised_split(prepared.raw_texts, prepared.labels, request, groups=prepared.connected_groups)
    def fit(texts, labels):
        return MultilingualTextClassifier(preparer=preparer, max_features=params['max_features'],
            minimum_document_frequency=params['minimum_document_frequency'], class_weight=params['class_weight']).fit(texts, labels)
    evaluation = fit(split.train_features, split.train_target)
    final = fit(prepared.raw_texts, prepared.labels)
    predictions = final.predict(incoming.message)
    probabilities = final.predict_proba(incoming.message)
    accuracy = float(np.mean(evaluation.predict(split.holdout_features) == split.holdout_target))
    item = {'name': call['arguments']['run_name'], 'params': params, 'saved_model_id': saved['trained_model_id'],
        'replayed_holdout_accuracy': accuracy, 'saved_holdout_accuracy': saved['evaluation']['details']['classification_report']['accuracy'],
        'holdout_batches': sorted(history.iloc[split.holdout_positions].customer_batch.unique().tolist()),
        'confirmation_correct': sum(p == truth[t] for p, t in zip(predictions, incoming.ticket_id)), 'count':len(incoming),
        'predictions': dict(zip(incoming.ticket_id, predictions.tolist()))}
    if saved['trained_model_id'] == 68:
        evidence['retained_holdout_rows'] = history.iloc[split.holdout_positions].to_dict(orient='records')
        evidence['retained_errors'] = []
        tokens = final.prepare(incoming.message)
        matrix = final.vectorizer.transform(tokens.prepared_texts.tolist())
        names = final.vectorizer.get_feature_names_out()
        for pos, row in incoming.iterrows():
            if predictions[pos] == truth[row.ticket_id]:
                continue
            predicted = int(np.flatnonzero(final.classes_ == predictions[pos])[0])
            expected = int(np.flatnonzero(final.classes_ == truth[row.ticket_id])[0])
            weights = np.asarray(matrix[pos].toarray())[0]
            contributions = weights * (final.model.coef_[predicted] - final.model.coef_[expected])
            active = np.flatnonzero(weights)
            evidence['retained_errors'].append({**row.to_dict(), 'prediction':predictions[pos], 'expected':truth[row.ticket_id],
                'confidence':float(probabilities[pos].max()), 'prepared_tokens':tokens.token_rows[pos],
                'unknown_tokens':[t for t in tokens.token_rows[pos] if t not in final.vectorizer.vocabulary_],
                'feature_margin_wrong_minus_correct':sorted([{'token':str(names[i]), 'margin':float(contributions[i])} for i in active], key=lambda x:-x['margin'])})
        evidence['negation_vocabulary'] = {t: t in final.vectorizer.vocabulary_ for t in ['no','not','only','but','没有','不','但是']}
        evidence['retained_evaluation_digest'] = saved['text_classification_evaluation'].get('prediction_digest')
    evidence['configurations'].append(item)

(Path(__file__).parent / 'routing-replay.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf8')
for item in evidence['configurations']:
    print(item['name'], item['replayed_holdout_accuracy'], item['saved_holdout_accuracy'], item['confirmation_correct'])
print(json.dumps(evidence['retained_errors'],ensure_ascii=False,indent=2))
