"""Paired-source retrieval and numbered pad matching without geometry mutation."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from kicad_tooling.hwrepo.cad_assets import (
    MissingFootprintError,
    inventory,
    plan_model_assignment,
    resolve_footprint,
)
from tests.support import reference_root

MODEL = '${KICAD10_3DMODEL_DIR}/Paired.3dshapes/TwoPin.step'
DESTINATION = '${KIPRJMOD}/cad/auto/TwoPin.step'
TRANSFORM = '(offset (xyz 1.25 -0.4 0.8)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 90))'
PADS = '''(pad "1" thru_hole rect (at 0 0) (size 1.7 1.7) (drill 1) (layers "*.Cu" "*.Mask"))
(pad "2" thru_hole circle (at 0 2.54) (size 1.7 1.7) (drill 1) (layers "*.Cu" "*.Mask"))'''
FOOTPRINT = f'(footprint "TwoPin" (layer "F.Cu") {PADS} (model "{MODEL}" {TRANSFORM}))'


def board(rotation: int = 0, bottom: bool = False, pad_text: str = PADS, model: str = '') -> str:
    sign = -1 if bottom else 1
    transformed = pad_text.replace('(at 0 0)', f'(at 0 0 {rotation})').replace(
        '(at 0 2.54)', f'(at 0 {sign * 2.54:g} {rotation})')
    side = 'B.Cu' if bottom else 'F.Cu'
    return f'''(kicad_pcb (version 20240108) (footprint "Paired:TwoPin" (layer "{side}")
(at 21.7 42.2 {rotation}) (property "Reference" "J1") (path "/sheet/symbol")
{transformed} {model}))'''


class CadAssetTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix='cad-assets-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / 'repository'
        shutil.copytree(reference_root(), self.root, ignore=shutil.ignore_patterns('.git'))
        self.library = self.base / 'installed'
        self.member = self.library / 'footprints/Paired.pretty/TwoPin.kicad_mod'
        self.member.parent.mkdir(parents=True)
        self.member.write_text(FOOTPRINT)
        self.model = self.library / '3dmodels/Paired.3dshapes/TwoPin.step'
        self.model.parent.mkdir(parents=True)
        self.model.write_bytes(b'ISO-10303-21;\nEND-ISO-10303-21;\n')

    def resolve(self):
        return resolve_footprint(self.root, 'controller', 'Paired:TwoPin', self.library)

    def test_resolves_only_authored_pair_and_preserves_transform(self) -> None:
        resolved = self.resolve()
        self.assertEqual(resolved.source_bytes, self.member.read_bytes())
        self.assertEqual(resolved.models[0].source_bytes, self.model.read_bytes())
        self.assertEqual(resolved.models[0].source_model_reference, MODEL)
        self.assertIn(TRANSFORM, resolved.models[0].model_expression)
        self.assertIn('Explicit paired CAD library', resolved.provenance)

    def test_front_rotations_and_bottom_preserve_all_original_geometry(self) -> None:
        resolved = self.resolve()
        for rotation, bottom in ((0, False), (90, False), (180, False), (180, True), (90, True)):
            with self.subTest(rotation=rotation, bottom=bottom):
                source = board(rotation, bottom)
                after = plan_model_assignment(source, 'J1', resolved, {MODEL: DESTINATION})
                expression = f'(model "{DESTINATION}" {TRANSFORM})'
                self.assertIn(expression, after)
                self.assertEqual(after.replace('\n    ' + expression + '\n  ', ''), source)
                self.assertEqual(plan_model_assignment(after, 'J1', resolved, {MODEL: DESTINATION}), after)

    def test_number_spacing_size_drill_and_scale_mismatch_are_refused(self) -> None:
        mutations = (('"2" thru_hole', '"3" thru_hole'), ('0 2.54', '0 2.5'),
                     ('1.7 1.7', '1.8 1.8'), ('(drill 1)', '(drill 0.9)'),
                     ('0 2.54', '0 5.08'))
        for old, new in mutations:
            with self.subTest(old=old, new=new), self.assertRaisesRegex(ValueError, 'geometry'):
                plan_model_assignment(board(pad_text=PADS.replace(old, new)), 'J1', self.resolve(), {MODEL: DESTINATION})

    def test_authored_existing_model_path_is_vendored_without_changing_geometry_or_transform(self) -> None:
        expression = f'(model "{MODEL}"\n  {TRANSFORM})'
        source = board(90, True, model=expression)
        after = plan_model_assignment(source, 'J1', self.resolve(), {MODEL: DESTINATION})
        self.assertEqual(after, source.replace(MODEL, DESTINATION))
        self.assertEqual(plan_model_assignment(after, 'J1', self.resolve(), {MODEL: DESTINATION}), after)

    def test_existing_different_transform_or_path_conflicts(self) -> None:
        for expression in (f'(model "{DESTINATION}" (scale (xyz 2 2 2)))',
                           '(model "${KIPRJMOD}/wrong.step")'):
            with self.subTest(expression=expression), self.assertRaisesRegex(ValueError, 'existing 3D assignment'):
                plan_model_assignment(board(model=expression), 'J1', self.resolve(), {MODEL: DESTINATION})

    def test_changed_footprint_identity_refused_even_when_pad_geometry_matches(self) -> None:
        with self.assertRaisesRegex(ValueError, 'identity'):
            plan_model_assignment(board().replace('Paired:TwoPin', 'Other:TwoPin'), 'J1', self.resolve(), {MODEL: DESTINATION})

    def test_missing_library_and_member_are_distinct_from_malformed_source(self) -> None:
        with self.assertRaises(MissingFootprintError):
            resolve_footprint(self.root, 'controller', 'Absent:TwoPin', self.library)
        self.member.unlink()
        with self.assertRaises(MissingFootprintError):
            self.resolve()
        self.member.write_text(FOOTPRINT.replace('"TwoPin"', '"Wrong"'))
        with self.assertRaisesRegex(ValueError, 'name differs') as caught:
            self.resolve()
        self.assertNotIsInstance(caught.exception, MissingFootprintError)

    def test_missing_declared_project_member_does_not_request_official_fallback(self) -> None:
        member = self.root / 'examples/projects/controller/kicad/Pilot.pretty/R_Test.kicad_mod'
        member.unlink()
        with self.assertRaisesRegex(ValueError, 'Declared project footprint is missing') as caught:
            resolve_footprint(self.root, 'controller', 'Pilot:R_Test')
        self.assertNotIsInstance(caught.exception, MissingFootprintError)

    def test_missing_model_never_guesses_from_an_unrelated_file(self) -> None:
        self.model.rename(self.model.with_name('Other.step'))
        with self.assertRaisesRegex(ValueError, 'model is missing'):
            self.resolve()

    def test_wrong_version_model_variable_and_escape_are_refused(self) -> None:
        for reference in ('${KICAD9_3DMODEL_DIR}/Paired.3dshapes/TwoPin.step',
                          '${KICAD10_3DMODEL_DIR}/../outside.step', '/private/tmp/part.step'):
            self.member.write_text(FOOTPRINT.replace(MODEL, reference))
            with self.subTest(reference=reference), self.assertRaises(ValueError):
                self.resolve()

    def test_symlinked_model_is_not_treated_as_copied_source(self) -> None:
        actual = self.model.with_name('real.step')
        self.model.rename(actual)
        self.model.symlink_to(actual)
        with self.assertRaisesRegex(ValueError, 'Linked CAD asset'):
            self.resolve()

    def test_model_multiple_authored_bodies_are_preserved(self) -> None:
        second = self.model.with_name('Second.step')
        second.write_bytes(b'ISO-10303-21; second fixture;')
        other = MODEL.replace('TwoPin.step', 'Second.step')
        self.member.write_text(FOOTPRINT[:-1] + f' (model "{other}" (offset (xyz 0 0 2)))' + ')')
        resolved = self.resolve()
        self.assertEqual(len(resolved.models), 2)
        after = plan_model_assignment(board(), 'J1', resolved, {MODEL: DESTINATION, other: DESTINATION.replace('TwoPin', 'Second')})
        self.assertEqual(after.count('(model '), 2)
        self.assertIn('(offset (xyz 0 0 2))', after)

    def test_nonfinite_authored_model_transform_refused(self) -> None:
        self.member.write_text(FOOTPRINT.replace('1.25', 'nan'))
        with self.assertRaisesRegex(ValueError, 'finite'):
            self.resolve()

    def test_hidden_model_and_missing_pair_are_actionable(self) -> None:
        self.member.write_text(FOOTPRINT[:-2] + '(hide yes)))')
        with self.assertRaisesRegex(ValueError, 'hidden'):
            self.resolve()
        self.member.write_text(f'(footprint "TwoPin" (layer "F.Cu") {PADS})')
        with self.assertRaisesRegex(ValueError, 'no paired 3D model'):
            self.resolve()

    def test_destination_mapping_is_complete_and_portable(self) -> None:
        for mappings in ({}, {MODEL: '/private/tmp/model.step'}, {MODEL: '${KIPRJMOD}/${UNKNOWN}/x.step'}):
            with self.subTest(mappings=mappings), self.assertRaises(ValueError):
                plan_model_assignment(board(), 'J1', self.resolve(), mappings)

    def test_environment_discovers_only_requested_standard_library(self) -> None:
        with patch.dict('os.environ', {'KICAD10_FOOTPRINT_DIR': str(self.library / 'footprints'),
                                       'KICAD10_3DMODEL_DIR': str(self.library / '3dmodels')}):
            resolved = resolve_footprint(self.root, 'controller', 'Paired:TwoPin')
        self.assertEqual(resolved.source_path, self.member)

    def test_inventory_records_board_orientation_and_models(self) -> None:
        path = self.root / 'examples/projects/controller/kicad/controller.kicad_pcb'
        path.write_text(board(90, True))
        result = inventory(self.root, 'controller')
        self.assertEqual(result.path, path)
        placed = result.footprints[0]
        self.assertEqual((placed.reference, placed.footprint_id, placed.layer, placed.rotation), ('J1', 'Paired:TwoPin', 'B.Cu', 90))
        self.assertEqual(placed.pads, self.resolve().pads)
        self.assertEqual(placed.instance_path, '/sheet/symbol')

    def test_source_geometry_also_checked_if_resolved_object_changes(self) -> None:
        resolved = self.resolve()
        changed = replace(resolved, pads=(replace(resolved.pads[0], drill=(0.8, 0.8)), *resolved.pads[1:]))
        with self.assertRaisesRegex(ValueError, 'drills'):
            plan_model_assignment(board(), 'J1', changed, {MODEL: DESTINATION})


if __name__ == '__main__':
    unittest.main()
