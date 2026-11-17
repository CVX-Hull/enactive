"""Production owner/channel/SQLite/player composition against independent SDL.

Run explicitly under the lead's native turn. This has no provider, host or game;
it cannot establish organic play, real host succession or game save/reload.
"""
import hashlib
import json
from pathlib import Path
import time
import uuid

from harness.application import Application
from harness.computer.launch import OwnedTarget
from harness.computer.runtime import ComputerRuntime
from harness.player.journal import Journal
from tests.computer_native_check import arguments,exclusion,records


def check(options):
    options.output.mkdir(parents=True,exist_ok=False)
    session=uuid.uuid4().hex
    target=dict(argv=[str(options.fixture),str(options.output/'events.jsonl'),'--hidden','--exit-after-ms','20000'],
        cwd=str(options.output),env=dict(DYLD_FRAMEWORK_PATH=str(options.resources),DYLD_LIBRARY_PATH=str(options.resources)))
    owner=OwnedTarget(options.output,session,target,options.library,options.output/'shared.lock',time.monotonic()+25)
    runtime=memory=None;report=dict(passed=False,scope=__doc__)
    try:
        owner.reserve();channel=owner.start()
        runtime=ComputerRuntime(options.output,session,channel,owner.process,owner.deadline,
            dict(max_inputs=30,max_requests=60,max_frames=60,max_bytes=2**31))
        memory=Journal(options.output/'player.sqlite3')
        app=Application(runtime,memory,options.output/'contexts',knowledge=Path(__file__).with_name('fixtures')/'empty-delivered-knowledge.json');actor=runtime.add_actor()
        owner.wait_target();exclusion(owner.shared_lock,True)
        def call(tool,args):return app.call(actor['token'],tool,dict(intent='Check the fixture through '+tool,**args),uuid.uuid4().hex)[0]
        end=time.monotonic()+3
        while True:
            observed=call('computer_observe',{})
            if observed['source'] is not None:break
            assert time.monotonic()<end,'No actual fixture image'
            time.sleep(.03)
        source=observed['source'];_,png=runtime.source(source['source_id'])
        hint=call('player_hint',dict(text='Fixture background from actual pixels',source_ids=[source['source_id']]))
        assert hint['schema']=='player-hint/1' and not any(r.get('key')==1073741903 for r in records(options.output/'events.jsonl'))
        moved=call('computer_input',dict(actions=[dict(type='key',key='RIGHT',modifiers=[])]))
        assert moved['status']=='completed' and moved['source']['source_id']!=source['source_id']
        assert any(row.get('key')==1073741903 and row.get('type')==768 for row in records(options.output/'events.jsonl'))
        ending=call('computer_input',dict(actions=[dict(type='key',key='ESC',modifiers=[])]))
        owner.process.wait(timeout=5)
        report.update(passed=True,initial_source=source,initial_png_sha256=hashlib.sha256(png).hexdigest(),
            hint=hint,direct_operation=moved,ending_operation=ending)
    finally:
        report['cleanup']=owner.close()
        if runtime is not None:runtime.store.close()
        if memory is not None:memory.close()
        (options.output/'check.json').write_text(json.dumps(report,indent=2)+'\n')
    assert report['cleanup']['native_absence_verified'] and report['cleanup']['normal_native_exit_zero'],report['cleanup']
    exclusion(owner.shared_lock,False)


if __name__=='__main__':check(arguments())
