# -*- coding: utf-8 -*-
import json
from contextlib import contextmanager

import mock
from nose.tools import eq_
from rest_framework.exceptions import ParseError
from zipfile import BadZipfile, ZipFile

from django.core.files.uploadedfile import TemporaryUploadedFile
from django.forms import ValidationError

from mkt.site.tests import TestCase
from mkt.extensions.validation import ExtensionValidator


class TestExtensionValidator(TestCase):
    """
    Tests the ExtensionValidator class. The following methods are tested in
    the TestExtensionViewSetPost test case instead, as part of an end-to-end
    workflow:

    * ExtensionValidator.validate_file
    * ExtensionValidator.validate_json
    * ExtensionValidator.validate_icon_files
    """
    def setUp(self):
        self.extension = None
        self.validator = ExtensionValidator()
        super(TestExtensionValidator, self).setUp()

    def tearDown(self):
        if self.extension:
            self.extension.close()

    @contextmanager
    def assertValidationError(self, key):
        """
        Context manager assertion which asserts that the yielded code raises an
        appropriate validation exception and message.

        Asserts:
        - That the exception is an instance of ParseError.
        - That the exception message's key matches the passed validation error
          key.
        - That the exception message's message string matches the message
          string for the passed validation error key.
        """
        try:
            yield
        except Exception, e:
            eq_(e.__class__, ParseError)
            eq_(e.detail['key'], key)
            eq_(e.detail['message'], ExtensionValidator.errors[key])
        else:
            self.fail('Does not raise a ParseError.')

    def _extension(self, data):
        self.extension = TemporaryUploadedFile('ext.zip', 'application/zip', 0,
                                               'UTF-8')
        with ZipFile(self.extension, "w") as z:
            if data is not None:
                z.writestr('manifest.json', json.dumps(data))
        return self.extension

    def test_full(self):
        extension_file = self._extension({
            'author': u'Me, Mŷself and I',
            'name': u'My Extënsion',
            'description': u'This is a valid descriptiôn',
            'version': '0.1.2.3',
        })
        try:
            self.validator = ExtensionValidator(extension_file)
            self.validator.validate()
        except ParseError as e:
            assert False, u'Got unexpected validation error: %s' % unicode(e)

    def test_calls(self):
        """
        This method tests that each validation method on ExtensionValidator is
        correctly called. Whenever adding a validation method, take care to
        include its name in the `validation_methods` list.
        """
        validation_methods = [
            'validate_author',
            'validate_description',
            'validate_file',
            'validate_icons',
            'validate_json',
            'validate_name',
            'validate_version',
        ]
        mocks = {method: mock.DEFAULT for method in validation_methods}
        with mock.patch.multiple(ExtensionValidator, **mocks):
            self.test_full()
            for method in validation_methods:
                mocked = getattr(ExtensionValidator, method)
                eq_(mocked.call_count, 1)

    def test_validate_file(self):
        manifest_data = {
            'name': u'My Extënsion',
        }
        extension_file = self._extension(manifest_data)
        manifest = self.validator.validate_file(extension_file)
        eq_(json.loads(manifest), manifest_data)

    def test_validate_file_wrong_content_type(self):
        extension_file = self._extension({'name': u'My Extënsion'})
        extension_file.content_type = 'application/wrong_content_type'
        with self.assertValidationError('BAD_CONTENT_TYPE'):
            self.validator.validate_file(extension_file)

    @mock.patch('mkt.extensions.validation.SafeUnzip.is_valid')
    def test_validate_file_unsafe_zip(self, is_valid_mock):
        extension_file = self._extension({'name': u'My Extënsion'})

        is_valid_mock.side_effect = ValidationError('oops')
        with self.assertRaises(ParseError):
            self.validator.validate_file(extension_file)

        is_valid_mock.side_effect = IOError
        with self.assertRaises(ParseError):
            self.validator.validate_file(extension_file)

        is_valid_mock.side_effect = BadZipfile
        with self.assertRaises(ParseError):
            self.validator.validate_file(extension_file)

    def test_validate_file_no_manifest(self):
        extension_file = self._extension(None)
        with self.assertValidationError('NO_MANIFEST'):
            self.validator.validate_file(extension_file)

    def test_validate_json_unicodeerror(self):
        with self.assertValidationError('INVALID_JSON_ENCODING'):
            self.validator.validate_json('{"name": "\x81"}')

    def test_validate_json_not_json(self):
        with self.assertValidationError('INVALID_JSON'):
            self.validator.validate_json('not json')

    def test_name_missing(self):
        with self.assertValidationError('NAME_MISSING'):
            self.validator.validate_name({})

    def test_name_not_string(self):
        with self.assertValidationError('NAME_NOT_STRING'):
            self.validator.validate_name({'name': 42})
        with self.assertValidationError('NAME_NOT_STRING'):
            self.validator.validate_name({'name': []})
        with self.assertValidationError('NAME_NOT_STRING'):
            self.validator.validate_name({'name': {}})
        with self.assertValidationError('NAME_NOT_STRING'):
            self.validator.validate_name({'name': None})

    def test_name_too_short(self):
        with self.assertValidationError('NAME_TOO_SHORT'):
            self.validator.validate_name({'name': ''})

    def test_name_only_whitespace(self):
        with self.assertValidationError('NAME_TOO_SHORT'):
            self.validator.validate_name({'name': '\n \t'})

    def test_name_too_long(self):
        with self.assertValidationError('NAME_TOO_LONG'):
            self.validator.validate_name({'name': u'ŷ' * 46})

    def test_name_valid(self):
        expected_name = u'My Lîttle Extension'
        try:
            self.validator.validate_name({'name': expected_name})
        except:
            assert False, u'A valid name "%s" fails validation' % expected_name

    def test_description_valid(self):
        expected_description = u'My very lîttle extension has a description'
        try:
            self.validator.validate_description(
                {'description': expected_description})
        except:
            assert False, (u'A valid description'
                           u' "%s" fails validation' % expected_description)

    def test_description_missing_valid(self):
        try:
            self.validator.validate_description({})
        except:
            assert False, u'Description should not be required.'

    def test_description_invalid(self):
        with self.assertValidationError('DESCRIPTION_NOT_STRING'):
            self.validator.validate_description({'description': 42})
        with self.assertValidationError('DESCRIPTION_NOT_STRING'):
            self.validator.validate_description({'description': []})
        with self.assertValidationError('DESCRIPTION_NOT_STRING'):
            self.validator.validate_description({'description': {}})
        with self.assertValidationError('DESCRIPTION_NOT_STRING'):
            self.validator.validate_description({'description': None})

    def test_description_too_long(self):
        with self.assertValidationError('DESCRIPTION_TOO_LONG'):
            self.validator.validate_description({'description': u'ô' * 134})

    def test_author_invalid(self):
        with self.assertValidationError('AUTHOR_NOT_STRING'):
            self.validator.validate_author({'author': 42})
        with self.assertValidationError('AUTHOR_NOT_STRING'):
            self.validator.validate_author({'author': []})
        with self.assertValidationError('AUTHOR_NOT_STRING'):
            self.validator.validate_author({'author': {}})
        with self.assertValidationError('AUTHOR_NOT_STRING'):
            self.validator.validate_author({'author': None})

    def test_author_only_whitespace(self):
        with self.assertValidationError('AUTHOR_TOO_SHORT'):
            self.validator.validate_author({'author': '\n \t'})

    def test_author_valid(self):
        expected_author = u'I am a famous aûthor'
        try:
            self.validator.validate_author(
                {'author': expected_author})
        except:
            assert False, (u'A valid author'
                           u' "%s" fails validation' % expected_author)

    def test_author_missing_valid(self):
        try:
            self.validator.validate_author({})
        except:
            assert False, u'Author should not be required.'

    def test_author_too_long(self):
        with self.assertValidationError('AUTHOR_TOO_LONG'):
            self.validator.validate_author({'author': u'ŷ' * 129})

    def test_version_valid(self):
        expected_version = u'0.42.42.42'
        try:
            self.validator.validate_version({'version': expected_version})
        except:
            assert False, (u'A valid version'
                           u' "%s" fails validation' % expected_version)

    def test_version_absent(self):
        with self.assertValidationError('VERSION_MISSING'):
            self.validator.validate_version({})

    def test_version_not_string(self):
        with self.assertValidationError('VERSION_NOT_STRING'):
            self.validator.validate_version({'version': 42})
        with self.assertValidationError('VERSION_NOT_STRING'):
            self.validator.validate_version({'version': 0.42})
        with self.assertValidationError('VERSION_NOT_STRING'):
            self.validator.validate_version({'version': []})
        with self.assertValidationError('VERSION_NOT_STRING'):
            self.validator.validate_version({'version': {}})
        with self.assertValidationError('VERSION_NOT_STRING'):
            self.validator.validate_version({'version': None})

    def test_version_too_many_dots(self):
        with self.assertValidationError('VERSION_INVALID'):
            self.validator.validate_version({'version': '0.42.42.42.42'})

    def test_version_contains_leading_zero(self):
        with self.assertValidationError('VERSION_INVALID'):
            self.validator.validate_version({'version': '0.42.042.42'})

    def test_version_contains_hexadecimal_number(self):
        with self.assertValidationError('VERSION_INVALID'):
            self.validator.validate_version({'version': '0.42.0x0.42'})

    def test_version_contains_a_non_number(self):
        with self.assertValidationError('VERSION_INVALID'):
            self.validator.validate_version({'version': '0.42.x42.42'})

    def test_version_contains_a_negative_number(self):
        with self.assertValidationError('VERSION_INVALID'):
            self.validator.validate_version({'version': '0.42.-42.42'})

    def test_version_contains_a_number_too_large(self):
        with self.assertValidationError('VERSION_INVALID'):
            self.validator.validate_version({'version': '0.42.65536.42'})

    def test_no_icons(self):
        try:
            self.validator.validate_icons({})
        except:
            self.fail('A missing icons object is allowed.')

    def test_empty_icons(self):
        try:
            self.validator.validate_icons({'icons': {}})
        except:
            self.fail('Empty icons object is allowed.')

    def test_icon_missing_128(self):
        with self.assertValidationError('ICONS_NO_128'):
            self.validator.validate_icons({'icons': {'64': ''}})

    def test_icon_not_png_extension(self):
        with self.assertValidationError('ICONS_INVALID_FORMAT'):
            self.validator.validate_icons({'icons': {'128': 'me.jpg'}})
