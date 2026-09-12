"""Infrastructure-only tests: stdlib, no setup, audio API or rendering."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('run_project', ROOT / 'scripts/run_project.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class InfrastructureTests(unittest.TestCase):
    def test_pacing(self):
        for minutes, target, count in [(12, 18, 40), (15, 22.5, 40), (20, 30, 40), (25, 30, 50)]:
            duration = minutes * 60
            actual = min(m.MAX_SCENE_S, max(m.MIN_SCENE_S, duration / m.MAX_SCENES))
            self.assertEqual(actual, target)
            cues = [{'start': i / 2, 'end': (i + 1) / 2, 'text': 'test'} for i in range(duration * 2)]
            self.assertEqual(len(m.group_scenes(cues, actual)), count)

    def test_tail_threshold(self):
        for tail, count in [(7, 1), (8, 2)]:
            cues = [{'start': 0, 'end': 20}, {'start': 20, 'end': 20 + tail}]
            self.assertEqual(len(m.group_scenes(cues, 20)), count)

    def test_regions_and_timing(self):
        for w, h in [(1920, 1080), (1360, 765), (3840, 2160)]:
            for ms in [8000, 18000, 22500, 30000, 30001]:
                ann = m.default_annotation('test', {'n': 1, 'caption': 'Ba bước'}, w, h, ms)
                end = 0
                previous_right = None
                durations = []
                for i, el in enumerate(ann['elements']):
                    self.assertEqual(el['sequence'], i + 1)
                    r, v = el['region'], el['reveal']
                    self.assertEqual(r['x'], round(w * [0, .345, .69][i]))
                    self.assertEqual(r['width'], int(w * .31))
                    if previous_right is not None:
                        self.assertGreaterEqual(r['x'] - previous_right, round(w * .035))
                    previous_right = r['x'] + r['width']
                    self.assertLessEqual(previous_right, w)
                    self.assertEqual(v['startMs'], end)
                    self.assertEqual(v['direction'], 'top_to_bottom')
                    durations.append(v['durationMs'])
                    end += v['durationMs']
                    for point in [el['handPath']['start'], el['handPath']['end']]:
                        self.assertTrue(r['x'] <= point[0] < previous_right)
                        self.assertTrue(0 <= point[1] < h)
                self.assertEqual(end, ms - m.GAZE_MS)
                self.assertLessEqual(max(durations) - min(durations), 1)

    def test_style_sync(self):
        style = (ROOT / 'references/style-lock.md').read_text()
        for section in ['Line', 'Fill', 'Character', 'Composition', 'CHARACTER LOCK', 'REGION LAW']:
            block = style.split('## ' + section + '\n', 1)[1].split('\n## ', 1)[0]
            for line in block.splitlines():
                if line.startswith('- ') or line.startswith('The character is '):
                    self.assertIn(line, m.PROMPT_TEMPLATE)
        self.assertIn('REGION LAW', m.PROMPT_TEMPLATE.format(narrative='Ba bước'))


if __name__ == '__main__':
    unittest.main()
