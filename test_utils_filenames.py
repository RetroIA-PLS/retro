import unittest

from utils import generar_nombre_archivo, get_activity_code


class FilenameGenerationTests(unittest.TestCase):
    def test_exact_database_activity_names_map_to_expected_codes(self):
        cases = [
            ("Actividad integradora uno. Tiempo de ahorrar", "AI1"),
            ("Actividad integradora dos. Construyendo carritos", "AI2"),
            ("Actividad integradora tres. Algebrando la vida", "AI3"),
            ("Actividad integradora cinco. Animales de granja", "AI5"),
            ("Actividad integradora seis. La caja", "AI6"),
            ("Foro de integración. El álgebra en la vida", "FI"),
            ("Proyecto integrador. Adelgazando costos", "PI"),
        ]
        for activity_name, expected_code in cases:
            with self.subTest(activity_name=activity_name):
                self.assertEqual(get_activity_code(activity_name), expected_code)
                self.assertTrue(generar_nombre_archivo("Mercedes", activity_name).endswith(f"_retro_{expected_code}"))

    def test_activity_code_normalizes_whitespace_and_case(self):
        self.assertEqual(get_activity_code("  aCtividad   integradora    UNO  "), "AI1")
        self.assertEqual(get_activity_code("  FORO   DE   INTEGRACIÓN  "), "FI")

    def test_activity_integradora_without_number_falls_back_to_ai(self):
        self.assertEqual(get_activity_code("Actividad integradora final"), "AI")

    def test_none_or_empty_activity_name_is_safe(self):
        self.assertEqual(get_activity_code(None), "Gen")
        self.assertEqual(get_activity_code(""), "Gen")
        self.assertEqual(generar_nombre_archivo("Mercedes", ""), "Mercedes_retro_Gen")

    def test_unrelated_activity_name_falls_back_to_gen(self):
        self.assertEqual(get_activity_code("Laboratorio de lectura"), "Gen")


if __name__ == "__main__":
    unittest.main()
