"""Freeze bounded evidence from local diagnostic runs."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from xenix.services.ml.preparation import membership_digest

ROOT = Path(__file__).resolve().parents[2]
PACKET = Path(__file__).parent
REPORTS = ROOT/'build/agent-harness-namespace-d7bbe8d/confirmation'

def read(path):
    return json.loads(path.read_text(encoding='utf8'))

def write(name, value):
    (PACKET/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')

replay = read(PACKET/'routing-replay.json')
report = read(next(REPORTS.glob('business.routing.*.json')))
saved = next(json.loads(raw)['report'] for raw in report['turns'][0]['delivery_evidence']
    if raw.startswith('{') and json.loads(raw).get('report'))
history = pd.read_csv(ROOT/'tests/e2e/agent_harness/fixtures/business_tasks/routing/confirmation/history.csv')
positions = np.flatnonzero(history.customer_batch.isin(replay['configurations'][0]['holdout_batches']))
replay['validation'] = {
    'holdout_membership_digest_matches':membership_digest(saved['split_facts']['source_dataset_snapshot_digest'],'holdout',positions)==saved['split_facts']['holdout_membership_digest'],
    'all_six_saved_holdout_scores_match':all(c['saved_holdout_accuracy']==c['replayed_holdout_accuracy'] for c in replay['configurations']),
}
table = next(json.loads(raw) for raw in report['turns'][1]['delivery_evidence'] if raw.startswith('{') and json.loads(raw).get('uri')=='artifact://180')
predictions = next(c['predictions'] for c in replay['configurations'] if c['saved_model_id']==68)
replay['validation']['all_30_saved_predictions_match'] = all(predictions[row['ticket_id']]==row['prediction'] for row in table['rows'])
probabilities = {row['ticket_id']:row['prediction_score'] for row in table['rows']}
replay['validation']['max_error_confidence_delta'] = max(abs(e['confidence']-probabilities[e['ticket_id']]) for e in replay['retained_errors'])
replay['retained_evaluation_digest'] = saved['evaluation']['details']['prediction_digest']
replay['limitations'] = 'Rebuilt materialized Parquet and production estimators; the original persisted model binary was deleted with its cell. Membership, scores and outputs were checked against saved evidence. The diagnostic snapshot fingerprint does not affect the v2 split, which uses real materialized content SHA.'
write('routing-replay.json',replay)

original = read(next(REPORTS.glob('business.restock.*.json')))
rows = read(PACKET/'restock-live-observations.json')
write('restock-live-observations.json',[row for row in rows if 'pending_llm_sampling' in row['output']])
log = (ROOT/'build/agent-harness-namespace-d7bbe8d/confirmation.log').read_text(encoding='utf8')
start = log.index('Operation failed: Binder Error:')
end = log.index('agent-harness-benchmark: case=business.restock',start)
(PACKET/'restock-original-error.log').write_text(log[start:end],encoding='utf8')
stages = [json.loads(line) for line in (ROOT/'build/restock-confirmation-diagnosis/stages.jsonl').read_text(encoding='utf8').splitlines()]
completed = next(row for row in stages if row['stage']=='completed')
result = {
    'original_run':original['run_id'],'original_failure_kind':original['failure_kind'],
    'original_last_usage_seconds':original['trace']['events'][-1]['started_offset_seconds'],
    'original_sampling_rounds':original['budget']['sampling_rounds_admitted'],
    'original_database_retained':False,
    'scripted_error_replay':'restock-error-replay.json',
    'live_probe':{'completed_seconds':completed['seconds'],
        'primary_gateway_entries':sum(row['stage']=='gateway_enter' for row in stages),
        'tokens':sum(row.get('reported_tokens') or 0 for row in completed['usage']),
        'original_error_reproduced':False,'original_timeout_reproduced':False,
        'score':'Not scored; subject-only diagnosis on current HEAD, not a replacement benchmark result.'},
    'conclusion':'After failed SQL persistence and the next pending placeholder, before the next metered main LLM gateway entry; original blocking frame remains unproven.',
    'next_evidence_needed':'Capture the active stack and canonical snapshot when pending sampling stops progressing before gateway entry; retain interrupted-cell evidence before cleanup.',
}
write('restock-evidence.json',result)
print(json.dumps({'routing':replay['validation'],'restock':result},ensure_ascii=False,indent=2))
