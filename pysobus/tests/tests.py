import os
import json
import unittest
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))

from pysobus import parser


class TestParser(unittest.TestCase):
    def setUp(self):
        self.parser = parser.Parser()

    def test_john_deere(self):
        test_file = os.path.join(os.path.dirname(__file__), 'jd.txt')
        self.__run_parse_test(test_file)

    def test_case(self):
        test_file = os.path.join(os.path.dirname(__file__), 'case.txt')
        self.__run_parse_test(test_file)

    def __run_parse_test(self, test_file):
        self.assertTrue(os.path.exists(test_file))
        with open(test_file, 'r') as fh:
            for line in fh:
                ts, message, pgn, expected = line.rstrip().split('\t')
                info = parser.msg_to_header_info_and_payload(message)
                parsed = self.parser.parse_message(message, float(ts))
                self.assertEqual(info['pgn'], int(pgn))
                if parsed:
                    self.assertEqual(parsed['spn_vals'], json.loads(expected))
                else:
                    self.assertEqual(None, json.loads(expected))


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestParser)
    unittest.TextTestRunner(verbosity=2).run(suite)
