"""One instrumented subject-only diagnostic run, separate from benchmark scores."""
import faulthandler
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time

from xenix.config import ensure_app_dirs, get_app_paths
from tests.e2e.agent_harness._infra.budgets import BenchmarkBudgetController, BenchmarkBudgetPolicy
from tests.e2e.agent_harness._infra.runner import _HeadlessBenchmarkCell, load_settings_snapshot, _effective_subject_settings
from tests.e2e.agent_harness.test_business_restock_decision import RestockDecisionTask

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'build/restock-confirmation-diagnosis'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    started = time.perf_counter()
    def record(name, **values):
        with (OUT/'stages.jsonl').open('a',encoding='utf8') as out:
            out.write(json.dumps({'stage':name,'seconds':time.perf_counter()-started,**values},ensure_ascii=False,default=str)+'\n')
        print(name,round(time.perf_counter()-started,3),flush=True)
    with (OUT/'stacks.txt').open('w',encoding='utf8') as stacks, TemporaryDirectory(prefix='xenix-restock-live-diagnosis-',ignore_cleanup_errors=True) as folder:
        faulthandler.dump_traceback_later(30,repeat=True,file=stacks)
        os.environ['XENIX_APP_HOME'] = folder
        settings,_ = load_settings_snapshot(ROOT/'build/agent-harness-namespace-d7bbe8d/settings/agent_settings.json')
        cell = _HeadlessBenchmarkCell(paths=ensure_app_dirs(get_app_paths()),settings=_effective_subject_settings(settings),embedding_settings=None,
            budget=BenchmarkBudgetController(BenchmarkBudgetPolicy()))
        record('graph_ready')
        original = cell.llm.stream
        def observed_stream(**kwargs):
            record('gateway_enter',messages=[m.model_dump(mode='json') for m in kwargs['messages']])
            for event in original(**kwargs):
                if getattr(event,'response',None) is not None:
                    record('gateway_response',response=event.response.model_dump(mode='json'))
                yield event
        cell.llm.stream = observed_stream
        try:
            thread = cell.create_thread(title='Restock confirmation diagnosis',fq_model_key=settings.default_fq_model_key)
            case = RestockDecisionTask('confirmation')
            submission = case.build_submissions(thread_id=thread,fq_model_key=settings.default_fq_model_key)[0]
            for event in cell.harness.submit_user_turn_stream(submission):
                record('harness_'+event.kind)
                if event.snapshot is not None:
                    (OUT/'snapshot.json').write_text(event.snapshot.model_dump_json(indent=2),encoding='utf8')
            record('completed',usage=cell.llm.sampling_responses)
        finally:
            cell.close()
            faulthandler.cancel_dump_traceback_later()

if __name__ == '__main__':
    main()
