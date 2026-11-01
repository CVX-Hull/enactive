"""Current basic-control and optional playing-service tool descriptions."""
from __future__ import annotations

from .computer.protocol import action_schema
from .player.contracts import level_abstain_schema, level_proposal_schema, record_schema, program_schema


def obj(properties, required=None):
    return dict(type='object',properties=properties,required=list(properties) if required is None else required,
                additionalProperties=False)


ID = dict(type='string',minLength=1,maxLength=128)
IDS = dict(type='array',items=ID,maxItems=32,uniqueItems=True)
EMPTY = obj({})
SELECTION = obj(dict(crop={'anyOf':[{'type':'null'},dict(type='array',items=dict(type='integer',minimum=0,maximum=16384),minItems=4,maxItems=4)]},
                     size=dict(type='array',items=dict(type='integer',minimum=1,maximum=96),minItems=2,maxItems=2)))


def tool_specs() -> dict:
    """One current schema. Descriptions guide use, never gate game meaning."""
    return {
        'computer_observe':('Capture actual owned target pixels and mechanical provenance. Interpret all game meaning yourself. Identical pixels are valid; a frame is not proof of useful progress.',EMPTY),
        'computer_input':('Send1..32 basic key/text/click/wait operations, then capture. Keys: printable ASCII or ENTER ESC UP DOWN LEFT RIGHT TAB BACKSPACE SPACE PAGEUP PAGEDOWN HOME END DELETE; modifiers explicit CTRL ALT SHIFT. Text≤31UTF8 bytes, application consumption unknown. Clicks require source_id actually issued to you and ORIGINAL full-image coordinates. Wait≤2s each/15s combined delays WALL time and sends no game input; it is not the game’s own wait command or proof an operation finished. Delivered means SDL events handed over, never useful success. Partial/unknown ends input: collect original ID, never replay/rearm.',
            obj(dict(actions=dict(type='array',items=action_schema(),minItems=1,maxItems=32),source_id={'anyOf':[ID,{'type':'null'}]}),['actions'])),
        'computer_result':('Collect the exact original mechanical operation and image, including late receipts. This never repeats input or restores authority. Use its operation_id after uncertain transport.',obj(dict(operation_id=ID))),
        'computer_stop':('Permanently fence further input for this run. This does not save, quit, win, undo input or permit another actor.',EMPTY),
        'player_source':('Read exact retained PNG bytes by source_id, from this session or explicitly remembered prior-session knowledge. Source availability is not proof you previously read it.',obj(dict(source_id=ID))),
        'player_memory_append':('Append your fallible claim, Work, decision, procedure, correction or candidate advice. Link actual source IDs/support records; referenced current images are remembered lazily. State quantities/progress/uncertainty in data. Correction names supersedes. Memory never grants control or certifies a save. Returned id is also this authoring request ID.',obj(dict(record=record_schema()))),
        'player_memory_read':('Read an exact player record and provenance, including superseded history. These are player assertions, not verified engine facts.',obj(dict(record_id=ID))),
        'player_memory_query':('Find up to50 player records. Default excludes superseded records; history remains readable. Use Work/claims/corrections to reconstruct your task, not engineering files.',
            obj(dict(kind=dict(type='string',enum=['claim','work','decision','procedure','correction','advice']),limit=dict(type='integer',minimum=1,maximum=50),include_superseded=dict(type='boolean')),[])),
        'player_memory_context':('Build a bounded whole-record support/correction/program-lineage context. Omissions and unread source references are explicit; missing knowledge grants no authority.',
            obj(dict(ids=IDS,max_bytes=dict(type='integer',minimum=1,maximum=65536)),['ids'])),
        'player_program_save':('Store your immutable JavaScript step(view,state) program, source/support provenance, applicability and optional parent revision. Sibling revisions can coexist. No dispatch or success is implied. Returned id is also this authoring request ID.',obj(dict(program=program_schema()))),
        'player_program_read':('Read an exact current program and its parent/source/support lineage. Applicability is fallible player knowledge.',obj(dict(program_id=ID))),
        'player_program_run':('Run your selected program locally, without an inference call per step. Each step sees program-view/3: actual source metadata, image.rgb flat RGB channels with image.width/height/crop/sampling/omissions, optional YOUR interpretation and original mechanical remaining resources. Source PNG is decoded through Pillow; only your selected crop/nearest view≤96x96 enters V8, alpha on black. Program returns {status:act|yield|done,state,actions,reason}; act uses the same basic controls, others actions:null. Click coordinates must map back to ORIGINAL full-image pixels. CPU/state/heap/time bounds apply; no hidden game facts, semantic eligibility, replay or budget renewal. Helper fault/yield permits direct input while custody remains healthy; partial/unknown stops. Result retains child operation/source IDs, final state and explicit trace omissions. Read full images/receipts with player_source/computer_result.',
            obj(dict(program_id=ID,initial_state=dict(type='object'),interpretation=dict(type='object'),selection=SELECTION,
                     max_steps=dict(type='integer',minimum=1,maximum=64),max_seconds=dict(type='number',exclusiveMinimum=0,maximum=20)),
                ['program_id','initial_state','interpretation','selection'])),
        'player_result':('Collect an original memory/program authoring or program-run service request after lost transport, without repeating it. Program runs retain original child IDs before input; collection adds available original receipts, never replays or restores custody.',obj(dict(operation_id=ID))),
        'player_handoff':('Seal this actor. No more input from this actor, and it carries no summary or knowledge snapshot. A successor requires actual host/MCP quiescence and retains original limits. This is actor custody only, not a game pause, save, identity check or new budget. Unknown input/user Pause cannot become handoff.',EMPTY),
        'player_log_read':('Read the served actor\'s operations in store order after a position: input key tokens, statuses and result source IDs, with pending operations marked and no source. Positions count from 1. During a handoff it returns no entries and handoff:true. The highest position you read binds your next commit.',
            obj(dict(after=dict(type='integer',minimum=0),limit=dict(type='integer',minimum=1,maximum=50)))),
        'player_level_commit':('Propose what to do with the current subgoal, the only Work you manage: keep it, close it with an outcome, or replace it with one new subgoal (and the outcome of the one it replaces). Software binds the position from your own log reads since your last commit attempt, and commits only if the served actor moved fewer than its staleness bound in inputs and has not handed off; otherwise the proposal is discarded. Committed records are fallible player data, not instructions or authority.',
            obj(dict(proposal=level_proposal_schema()))),
        'player_level_abstain':('End this pass without a proposal when the evidence does not support keeping, replacing or closing the subgoal. Nothing is written.',
            level_abstain_schema()),
        'player_intent':('Host-internal: the latest committed subgoal and its age, read by the actor host to build its request-only intent tail. Not offered to the model.',EMPTY),
    }


# Called by a host itself, never offered to the model; excluded from every enabled-tools table.
HOST_TOOLS = ('player_intent',)
# Tool names per capability class. The custodian enforces these as well as each host's enabled tools.
PROFILES = {
    'flat': ('computer_observe','computer_input','computer_result','computer_stop','player_source',
             'player_memory_append','player_memory_read','player_memory_query','player_memory_context',
             'player_program_save','player_program_read','player_program_run','player_result','player_handoff',
             'player_intent'),
    'narrowed': ('computer_observe','computer_input','computer_result','computer_stop','player_source',
                 'player_program_read','player_program_run','player_result','player_handoff','player_intent'),
    'reader': ('computer_result','player_source','player_memory_read','player_memory_query','player_memory_context',
               'player_program_read','player_result','player_log_read','player_level_commit','player_level_abstain'),
}
