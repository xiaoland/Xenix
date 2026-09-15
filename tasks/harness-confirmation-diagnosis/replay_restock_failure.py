"""Replay the observed DuckDB error class through the headless production graph."""
import faulthandler
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.agent import SubmitUserTurnInput, SourceAttachmentInput
from xenix.services.llm.providers import ProviderResponse, ProviderStreamEvent, ProviderToolCall
from xenix.services.llm import LLMSettings
from tests.e2e.agent_harness._infra.budgets import BenchmarkBudgetController, BenchmarkBudgetPolicy
from tests.e2e.agent_harness._infra.runner import _HeadlessBenchmarkCell

ROOT = Path(__file__).resolve().parents[2]
events = []
requests = []
faulthandler.dump_traceback_later(20, repeat=True)
started = time.perf_counter()
with TemporaryDirectory(prefix='xenix-restock-error-probe-', ignore_cleanup_errors=True) as folder:
    os.environ['XENIX_APP_HOME'] = folder
    cell = _HeadlessBenchmarkCell(paths=ensure_app_dirs(get_app_paths()), settings=LLMSettings(),
        embedding_settings=None, budget=BenchmarkBudgetController(BenchmarkBudgetPolicy()))
    try:
        def stream(**kwargs):
            messages = kwargs['messages']
            requests.append({'roles':[m.role for m in messages], 'last_result': messages[-1].tool_result_value})
            index = len(requests)
            print('gateway entry',index,round(time.perf_counter()-started,3),flush=True)
            if index == 1:
                tool = 'agent.tools.activate'
                args = {'names':['data.query']}
            elif index in [2,3]:
                dataset = cell.datasets.list_datasets()[0]
                tool = 'data.query'
                args = {'datasets':{'o':dataset.id}, 'sql':('SELECT range(0, 3) * 1.5 AS cost FROM o LIMIT 1' if index==2 else 'SELECT batches * 1.5 AS cost FROM o, unnest(range(0, 3)) AS q(batches) LIMIT 1')}
            else:
                yield ProviderStreamEvent(response=ProviderResponse(assistant_content_blocks=[{'type':'text','text':'计算完成。'}]))
                return
            yield ProviderStreamEvent(response=ProviderResponse(tool_calls=[ProviderToolCall(provider_call_id=f'call_{index}',
                tool_name=tool,provider_name=tool.replace('.','_'),arguments=args)]))
        cell.llm.stream = stream
        thread = cell.harness.create_thread(title='Offline SQL recovery diagnosis')
        submission = SubmitUserTurnInput(thread_id=thread.thread.id, text='计算报价。',source_attachments=[SourceAttachmentInput(file_path=str(ROOT/'tests/e2e/agent_harness/fixtures/business_tasks/restock/confirmation/offers.csv'))])
        for event in cell.harness.submit_user_turn_stream(submission):
            events.append({'kind':event.kind,'seconds':time.perf_counter()-started})
            print('event',event.kind,flush=True)
        result = {'provider_requests':len(requests),'events':events, 'requests':requests,'elapsed_seconds':time.perf_counter()-started,
            'limitation':'Scripted responses and minimal SQL reproduce the logged BinderException class, not the unavailable original SQL/history.'}
        (Path(__file__).parent/'restock-error-replay.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    finally:
        cell.close()
faulthandler.cancel_dump_traceback_later()
