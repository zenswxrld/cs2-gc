import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import native_finishes as finishes
import study_skins
from test_native_finishes import compmat, material


class StudySkins(unittest.TestCase):
    def test_reads_composite_and_named_material_parameters(self):
        with tempfile.TemporaryDirectory() as folder:
            vmat = 'materials/models/weapons/customization/paints/vmats/am_zebra.vmat'
            for path, data in {'weapons/paints/legacy/am_zebra.vcompmat_c': compmat(vmat),
                               vmat + '_c': material(vmat, [[.1, .2, .3, 1]] * 4)}.items():
                (Path(folder) / path).parent.mkdir(parents=True, exist_ok=True)
                (Path(folder) / path).write_bytes(data)
            kits = study_skins.paint_kits('"items_game" { "paint_kits" { "200" { "name" "am_zebra" "style" "5" } '
                                          '"201" { "name" "am_gone" "style" "2" } } }')
            rows = study_skins.study(finishes.Source(folder=folder), kits, {'am_zebra': {'weapon_ak47'}})
        zebra = rows['am_zebra']
        self.assertEqual(zebra['weapons'], ['weapon_ak47'])
        self.assertEqual(zebra['values']['style'], '5')
        params = zebra['materials'][vmat]
        self.assertEqual(params['m_shaderName'], 'csgo_customweapon.vfx')
        self.assertEqual(params['m_textureParams'][0]['m_name'], 'g_tPattern')
        self.assertEqual([round(v, 3) for v in params['m_vectorParams'][0]['m_value']], [.1, .2, .3, 1])
        self.assertTrue(rows['am_gone']['missing'])


if __name__ == '__main__':
    unittest.main()
