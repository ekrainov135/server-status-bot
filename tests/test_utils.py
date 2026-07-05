"""Unit tests for `app.utils`.

`merge_with_concat` is a pure function (no I/O, no mocking needed) that
merges the shared `common.yaml` locale strings with a language-specific
locale file, concatenating values present in both. It underpins every
button label and header in the bot, so a regression here silently breaks
the whole UI text layer.
"""

from app.utils import merge_with_concat


class TestMergeWithConcat:
    def test_key_only_in_common_is_kept_as_is(self):
        common = {'reboot': '\u2757'}
        locale = {}

        assert merge_with_concat(common, locale) == {'reboot': '\u2757'}

    def test_key_only_in_locale_is_kept_as_is(self):
        common = {}
        locale = {'reboot': 'Reboot'}

        assert merge_with_concat(common, locale) == {'reboot': 'Reboot'}

    def test_key_present_in_both_is_concatenated_common_first(self):
        common = {'reboot': '\u2757'}
        locale = {'reboot': 'Reboot'}

        assert merge_with_concat(common, locale) == {'reboot': '\u2757 Reboot'}

    def test_disjoint_keys_from_both_sides_are_all_present(self):
        common = {'a': 'A'}
        locale = {'b': 'B'}

        result = merge_with_concat(common, locale)

        assert result == {'a': 'A', 'b': 'B'}

    def test_empty_inputs_produce_empty_dict(self):
        assert merge_with_concat({}, {}) == {}

    def test_does_not_mutate_input_dicts(self):
        common = {'a': 'A', 'shared': 'C'}
        locale = {'b': 'B', 'shared': 'L'}

        merge_with_concat(common, locale)

        assert common == {'a': 'A', 'shared': 'C'}
        assert locale == {'b': 'B', 'shared': 'L'}
