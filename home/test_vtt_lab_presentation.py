"""Pure metadata limits; no network calls or configured database."""
from copy import deepcopy
import unittest
from home.vtt_lab_presentation import validate_presentation


def config():
    return {'background':{'url':'/static/map.webp','cell_px':64,'origin_x':0,'origin_y':0,'opacity':1},
            'grid_opacity':0.25}


class PresentationTests(unittest.TestCase):
    def test_explicit_clear_and_independent_copy(self):
        self.assertEqual(validate_presentation({'background':None,'grid_opacity':0}),
                         {'background':None,'grid_opacity':0})
        original=config();before=deepcopy(original)
        result=validate_presentation(original)
        result['background']['origin_x']=99
        self.assertEqual(original,before)

    def test_calibration_allows_fractional_pixels_and_negative_origin(self):
        value=config();value['background'].update(cell_px=30.5,origin_x=-123.25,origin_y=4096.5)
        self.assertEqual(validate_presentation(value),value)

    def test_url_policy_rejects_executable_embedded_credentials_and_http(self):
        for url in ('javascript:alert(1)','data:image/png;base64,abc','file:///C:/secret',
                    '//other.test/map.png','https://user:secret@host/map.png',
                    'http://host/map.png','https://host/\\evil','https://host/map.png\n',
                    ' https://host/map.png','/not-an-asset/map.png'):
            with self.subTest(url=url),self.assertRaises(ValueError):
                value=config();value['background']['url']=url;validate_presentation(value)
        for url in ('https://example.test/map.webp','/static/map.png','/media/map.jpg'):
            value=config();value['background']['url']=url
            self.assertEqual(validate_presentation(value)['background']['url'],url)

    def test_all_numeric_fields_are_finite_and_bounded(self):
        for key,invalid in [('cell_px',[0,-1,4097,True,float('nan'),float('inf'),'64']),
                            ('origin_x',[-32769,32769,False,float('nan')]),
                            ('origin_y',[-32769,32769,{},None]),('opacity',[-1,1.1,True,'1'])]:
            for bad in invalid:
                with self.subTest(key=key,value=bad),self.assertRaises(ValueError):
                    value=config();value['background'][key]=bad;validate_presentation(value)
        for bad in (-1,1.1,True,float('nan'),None):
            with self.assertRaises(ValueError):validate_presentation({'background':None,'grid_opacity':bad})

    def test_exact_shape_and_url_length_are_required(self):
        for value in ({},[],None,{'background':None,'grid_opacity':0,'terrain':{}},
                      {'background':{'url':'/static/a.png'},'grid_opacity':1}):
            with self.assertRaises(ValueError):validate_presentation(value)
        value=config();value['background']['url']='https://host/'+('a'*2048)
        with self.assertRaises(ValueError):validate_presentation(value)


if __name__=='__main__':unittest.main()
