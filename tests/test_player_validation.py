"""Local tool diagnostics and exact cached detail; no native gameplay."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from harness.gameplay.contracts import ContractError
from harness.gameplay.mission_requests import compose_request
from harness.player_tools import DETAIL_SECTIONS, PlayerTools
from tests.test_mission_request_producer import bundle, snapshot
from tests.test_player_claims import StagingClient
from tests.test_player_procedures import MECHANICAL
from tests.test_procedures import procedure


class PlayerValidationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / '.runtime').mkdir()
        self.client = StagingClient(self.root)
        self.player = PlayerTools(self.client)
        self.source = bundle()
        self.selected = dict(snapshot_id='chosen', mission=snapshot(), source=self.source, native={})
        self.player.snapshots['chosen'] = deepcopy(self.selected)

    def skill(self, **changes):
        intent = dict(skill_kind='direct', goal=dict(input=dict(type='key', key='i', modifiers=[]),
            intent='Inspect inventory', expected='Inventory appears', interrupt_allowed=False),
            work_id=None, perception=None, procedure=None)
        intent.update(changes)
        return dict(snapshot_id='chosen', scope='new_root', source_id=None, supporting_source_ids=[],
            limits=dict(primitives=1, wall_seconds=7, game_seconds=10), intent=intent)

    def refused(self, name, arguments):
        original = deepcopy(arguments)
        messages = []
        for sdk in (False, True):
            with self.subTest(sdk=sdk):
                data = deepcopy(arguments)
                if sdk:
                    data.update(request_id='explicit', wait_seconds=0)
                with self.assertRaises(ContractError) as caught:
                    (self.player.call if sdk else self.player.model_arguments)(name, data)
                message = str(caught.exception)
                self.assertLessEqual(len(message), 1600)
                self.assertNotIn('private-player-payload', message)
                messages.append(message)
                self.assertEqual(self.client.events, [])
                self.assertEqual(self.client.writes, [])
                self.assertFalse((self.root / '.runtime/mission-requests').exists())
        self.assertEqual(arguments, original)
        return messages

    def test_direct_description_reports_selected_goal_fields_without_unrelated_branches(self):
        args = self.skill(goal=dict(description='private-player-payload' * 100))
        for message in self.refused('enactive_skill', args):
            for field in ('input', 'intent', 'expected', 'interrupt_allowed'):
                self.assertIn(field, message)
            self.assertIn('intent.goal', message)
            self.assertIn('required', message)
            self.assertNotIn('navigate', message)
            self.assertNotIn('javascript', message)
            self.assertNotIn('target', message)

    def test_program_goal_type_and_extra_field_errors_use_program_branch(self):
        args = self.skill(skill_kind='program', goal=dict(state=[], intent='private-player-payload',
            expected='Visible progress', extra='private-player-payload'))
        for message in self.refused('enactive_skill', args):
            self.assertIn('intent.goal.state', message)
            self.assertIn('object', message)
            self.assertIn('unexpected', message.lower())
            self.assertNotIn('input', message)
            self.assertNotIn('navigate', message)

    def test_procedure_authoring_reports_nested_program_error_without_claim_fields(self):
        entry = {key: value for key, value in procedure().items() if key not in MECHANICAL}
        entry['program'] = dict(language='javascript/1', source=['private-player-payload'])
        args = dict(snapshot_id='chosen', intent=dict(entry_type='procedure', entry=entry))
        for message in self.refused('enactive_remember', args):
            self.assertIn('intent.entry.program.source', message)
            self.assertIn('string', message)
            self.assertNotIn('grounding', message)
            self.assertNotIn('supports', message)

    def test_correction_errors_use_claim_shape(self):
        args = dict(snapshot_id='chosen', intent=dict(entry_type='claim', entry={}, retired_ids=[],
            reason='private-player-payload'))
        for message in self.refused('enactive_correct', args):
            self.assertIn('intent.entry', message)
            self.assertIn('required', message)
            self.assertNotIn('applicability', message)
            self.assertNotIn('on_unexpected', message)

    def test_unknown_missing_and_nonobject_discriminators_are_bounded(self):
        for name, discriminator in (('enactive_skill', 'skill_kind'), ('enactive_remember', 'entry_type'),
                                    ('enactive_correct', 'entry_type')):
            for intent in ({}, {discriminator: 'private-player-payload' * 100},
                           {discriminator: []}, 'private-player-payload'):
                with self.subTest(name=name, intent=intent):
                    args = self.skill() if name == 'enactive_skill' else dict(snapshot_id='chosen')
                    args['intent'] = intent
                    for message in self.refused(name, args):
                        self.assertIn(discriminator, message)

    def test_valid_direct_model_and_sdk_payload_preserve_exact_composition(self):
        arguments = self.skill()
        original = deepcopy(arguments)
        sdk, collection = self.player.model_arguments('enactive_skill', arguments)
        self.assertEqual({key: value for key, value in sdk.items()
                          if key not in ('request_id', 'wait_seconds')}, original)
        expected = compose_request(self.selected['mission'], request_id=sdk['request_id'],
            intent=dict(kind='skill', **original['intent']), limits=original['limits'],
            scope='new_root', source=self.source, supporting_source_ids=[])
        self.player.call('enactive_skill', sdk)
        self.assertEqual(self.client.writes, [expected])
        self.assertEqual(collection['arguments']['operation_id'], sdk['request_id'])
        self.assertEqual(arguments, original)


class MissionDetailTests(unittest.TestCase):
    def test_selected_mission_detail_is_complete_immutable_and_never_refreshes(self):
        original = snapshot(configuration=dict(original='configuration'), metrics=dict(primitives=3),
            last_receipt=dict(reason='original'), extra_future_field=dict(value=['complete']))
        client = Mock()
        client.status.return_value = dict(mission=original)
        player = PlayerTools(client)
        selected, _ = player.call('enactive_snapshot', {})
        expected = deepcopy(selected['mission'])
        original['extra_future_field']['value'].append('new status')
        player.call('enactive_snapshot', {})
        client.reset_mock()
        self.assertIn('mission', DETAIL_SECTIONS)
        for _ in range(2):
            detail, image = player.call('enactive_detail', dict(snapshot_id=selected['snapshot_id'],
                                                              section='mission'))
            self.assertEqual(detail['detail'], expected)
            self.assertFalse(detail['grants_authority'])
            self.assertIsNone(image)
            detail['detail']['extra_future_field']['value'].append('returned mutation')
        self.assertEqual(player.snapshots[selected['snapshot_id']]['mission'], expected)
        self.assertEqual(client.mock_calls, [])


if __name__ == '__main__':
    unittest.main()
