"""Published program shapes checked against the real passive evaluator, not play."""
import asyncio
import json
import unittest
from unittest.mock import Mock

from mcp import Client

from harness.gameplay.contracts import ContractError, validate_json
from harness.gameplay.native_input import validate_input
from harness.gameplay.policy_program import PolicyProgram, PolicyProgramError, program_result_schema
from harness.mission_client import MissionClient
from harness.player_mcp import make_server
from harness.player_tools import PlayerTools, tool_specs


class ProgramContractPresentationTests(unittest.TestCase):
    def setUp(self):
        self.specs = tool_specs()
        self.skill = next(s for s in self.specs if s.name == 'enactive_skill')
        line = self.skill.description.split('\nProgram result schema: ', 1)[1].splitlines()[0]
        self.published = json.loads(line)

    def evaluate(self, value):
        code = 'function step(view,state) { return ' + json.dumps(value) + '; }'
        with PolicyProgram(code) as program:
            return program.step({}, {})

    def test_published_key_text_click_and_stop_shapes_match_real_evaluation(self):
        values = [
            dict(status='act', state={}, input=dict(type='key', key='ENTER', modifiers=[]), reason='Fictional invocation'),
            dict(status='act', state={}, input=dict(type='text', text='sample'), reason='Fictional text'),
            dict(status='act', state={}, input=dict(type='click', button='left', x=1, y=2), reason='Fictional pixel'),
            dict(status='yield', state={}, input=None, reason='Need current evidence'),
            dict(status='done', state={}, input=None, reason='Terminated, effect unverified'),
        ]
        self.assertEqual(self.published, program_result_schema())
        for value in values:
            with self.subTest(value=value):
                validate_json(value, self.published)
                self.assertEqual(self.evaluate(value), value)
                if value['status'] == 'act' and value['input']['type'] != 'click':
                    self.assertEqual(validate_input(value['input'], text_limit=24), value['input'])
        click = values[2]['input']
        with self.assertRaises(ContractError):
            validate_input(click)
        direct = {**click, 'geometry': dict(window_width=10, window_height=10,
            output_width=10, output_height=10, viewport=[0, 0, 10, 10])}
        self.assertEqual(validate_input(direct), direct)

    def test_bad_returns_are_rejected_by_published_shape_and_evaluator(self):
        key = dict(type='key', key='ENTER', modifiers=[])
        bad = [
            dict(status='act', state={}, input=dict(key='ENTER', modifiers=[]), reason='Missing type'),
            dict(status='act', state={}, input=dict(type='key', key='ENTER'), reason='Missing modifiers'),
            dict(status='act', state={}, input=None, reason='Act cannot wait with null'),
            dict(status='yield', state={}, input=key, reason='Yield cannot propose input'),
            dict(status='done', state={}, input=key, reason='Done cannot propose input'),
            dict(status='act', state={}, input=dict(type='click', button='left', x=1, y=2,
                geometry={}), reason='Program cannot supply geometry'),
        ]
        for value in bad:
            with self.subTest(value=value):
                with self.assertRaises(ContractError):
                    validate_json(value, self.published)
                with self.assertRaises(PolicyProgramError):
                    self.evaluate(value)

    def test_export_is_deeply_isolated_from_evaluator_and_later_readers(self):
        exported = program_result_schema()
        exported['required'].clear()
        exported['then']['properties']['input']['anyOf'][0]['required'].clear()
        self.assertEqual(program_result_schema(), self.published)
        with self.assertRaises(PolicyProgramError):
            self.evaluate(dict(status='act', state={}, input=dict(key='ENTER'), reason='Still invalid'))

    def test_real_mcp_metadata_retains_order_schema_description_and_annotations(self):
        transport = Mock(spec=MissionClient)
        player = PlayerTools(transport)

        async def discover():
            async with Client(make_server(player)) as client:
                return (await client.list_tools()).tools

        tools = asyncio.run(discover())
        self.assertEqual([t.name for t in tools], [s.name for s in self.specs])
        for actual, spec in zip(tools, self.specs):
            self.assertEqual(actual.input_schema, spec.schema)
            self.assertEqual(actual.description, spec.description)
            self.assertEqual(actual.annotations.read_only_hint, spec.read_only)
        transport.assert_not_called()
        self.assertEqual(transport.mock_calls, [])


if __name__ == '__main__':
    unittest.main()
