"""BEA pointer tables and inline records, using synthetic archives."""
from pathlib import Path
import ast
import struct
import sys
import unittest

source = Path(__file__).resolve().parents[1] / 'tools/shader_split.py'
tree = ast.parse(source.read_text())
function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'bea_members')
def red(message): raise ValueError(message)
namespace = {'struct': struct, 'ZSTD_MAGIC': bytes.fromhex('28b52ffd'), 'red': red}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
bea_members = namespace['bea_members']


class BeaTests(unittest.TestCase):
    def test_archive_versions(self):
        for version in (0x10100, 0x60000):
            with self.subTest(version=hex(version)):
                data = bytearray(1024)
                data[:4] = b'SCNE'
                struct.pack_into('<I', data, 8, version)
                struct.pack_into('<QQ', data, 0x20, 2, 0x80)
                expected = [('one.bnsh', b'first'), ('two.bin', b'second')]
                for i, (name, content) in enumerate(expected):
                    entry = 0x80 + i * 0x48 if version == 0x60000 else 0x100 + i * 0x30
                    if version == 0x10100:
                        struct.pack_into('<Q', data, 0x80 + 8 * i, entry)
                    data[entry:entry + 4] = b'ASST'
                    struct.pack_into('<II', data, entry + 0x14, len(content), len(content))
                    offset, name_offset = 0x300 + i * 0x40, 0x200 + i * 0x40
                    struct.pack_into('<QQ', data, entry + (0x38 if version == 0x60000 else 0x20), offset, name_offset)
                    struct.pack_into('<H', data, name_offset, len(name))
                    data[name_offset + 2:name_offset + 2 + len(name)] = name.encode()
                    data[offset:offset + len(content)] = content
                self.assertEqual(list(bea_members(data, 'synthetic')), expected)


if __name__ == '__main__':
    unittest.main()
