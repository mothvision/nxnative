"""Production reflection conversion with synthetic translator descriptors."""
import ast
from pathlib import Path
import re
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import dmsh_geometry


def builder_reflection():
    # Isolate pure reflection code from the builder's CLI/profile initialization.
    tree = ast.parse((TOOLS / 'dmsh_build.py').read_text())
    names = {'reflect', 'decode_tex', 'decode_ubo_tex', 'const_sampler', 'c2_array', 'drv_reads', 'unfillable'}
    selected = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name in names)
                or (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ('SSBO', 'DRV_FILL', 'TEX_BASE') for target in n.targets for t in ast.walk(target)))]
    ns = {'re': re, 'dmsh_geometry': dmsh_geometry}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(TOOLS / 'dmsh_build.py'), 'exec'), ns)
    return ns


BUILDER = builder_reflection()
REFLECT = BUILDER['reflect']


def bindings(stage, offsets, flags, cb_slot=0):
    source = 'struct spvDescriptorSetBuffer0\n{\n' + ''.join(
        f'    device uint* gp_s{i} [[id({i})]];\n' for i in range(len(offsets))) + '};\n'
    res = {'sbufs': [{'binding': 40 + i, 'slot': i, 'cb_slot': cb_slot,
                      'cb_offset': off // 4, 'flags': flag}
                     for i, (off, flag) in enumerate(zip(offsets, flags))]}
    return REFLECT('synthetic', stage, source, res)


class DriverReads(unittest.TestCase):
    def test_every_stage_records_driver_offsets(self):
        for stage in ('vp', 'fp', 'cp', 'gp', 'tcp', 'tep'):
            with self.subTest(stage=stage):
                src = f'(*args.{stage}_c0)._m0[100].y + (*args.{stage}_c2)._m0[8u].x'
                self.assertEqual(BUILDER['drv_reads'](src), {
                    '0': {'vec4_offsets': [0x640], 'dynamic': False},
                    '2': {'vec4_offsets': [0x80], 'dynamic': False}})

    def test_runtime_driver_rows_are_fillable(self):
        for offset in (0x150, 0x200, 0x210, 0x610, 0x640):
            with self.subTest(offset=offset):
                self.assertEqual(BUILDER['unfillable']({'0': {'vec4_offsets': [offset], 'dynamic': False}}), [])
        self.assertEqual(BUILDER['unfillable']({'0': {'vec4_offsets': [0x700], 'dynamic': False}}), ['c0+0x700'])

    def test_dynamic_and_duplicate_reads(self):
        src = '(*a.vp_c0)._m0[i] + (*a.cp_c0)._m0[21] + (*a.vp_c0)._m0[21u]'
        self.assertEqual(BUILDER['drv_reads'](src), {
            '0': {'vec4_offsets': [0x150], 'dynamic': True}})
        self.assertEqual(BUILDER['drv_reads']('(*a.vp_c1)._m0[100]'), {})


class StorageBuffers(unittest.TestCase):
    def test_geometry_driver_table_offsets(self):
        got = bindings('gs', [0x410, 0x430], [1, 1])
        self.assertEqual([(b['kind'], b['reg']) for b in got], [('sbuf', 0), ('sbuf', 2)])

    def test_write_flag_from_translator_json(self):
        # BufferUsageFlags.Write = 1 << 0; Program.cs serializes it unchanged.
        got = bindings('cs', [0x310, 0x320], [1, 0])
        self.assertEqual([b['rw'] for b in got], [True, False])

    def test_write_flag_for_address_in_guest_uniform(self):
        got = bindings('gs', [0x38], [1], cb_slot=3)
        self.assertEqual((got[0]['kind'], got[0]['reg'], got[0]['off'], got[0]['rw']),
                         ('sbuf_ubo', 0, 0x38, True))

    def test_existing_stage_tables(self):
        for stage, base in [('vs', 0x110), ('cs', 0x310), ('ps', 0x510)]:
            with self.subTest(stage=stage):
                got = bindings(stage, [base, base + 15 * 16], [0, 0])
                self.assertEqual([b['reg'] for b in got], [0, 15])

    def test_unknown_or_unaligned_offsets_stay_unresolved(self):
        self.assertIsNone(bindings('gs', [0x414], [1])[0]['reg'])
        self.assertIsNone(bindings('hs', [0x410], [1])[0]['reg'])


if __name__ == '__main__':
    unittest.main()
