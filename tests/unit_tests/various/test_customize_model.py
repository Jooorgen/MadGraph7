################################################################################
#
# Copyright (c) 2009 The MadGraph7 Development team and Contributors
#
# This file is a part of the MadGraph7 project, an application which
# automatically generates Feynman diagrams and matrix elements for arbitrary
# high-energy processes in the Standard Model and beyond.
#
# It is subject to the MadGraph7 license which should accompany this
# distribution.
#
# For more information, visit madgraph.phys.ucl.ac.be and amcatnlo.web.cern.ch
#
################################################################################
"""Unit tests for the customize_model command"""

from __future__ import absolute_import
import io

import tests.unit_tests as unittest

import madgraph.interface.madgraph_interface as mg_interface
import models.build_restriction_lib as build_restrict_lib
import models.check_param_card as check_param_card
import models.import_ufo as import_ufo
import models.write_param_card as param_writer


def get_option(categories, name):
    for category in categories:
        for option in category:
            if option.name == name:
                return option
    return None


#===============================================================================
# The generic (model independent) options
#===============================================================================
class TestGenericCategories(unittest.TestCase):
    """The mass scheme options are built from the content of the model"""

    @classmethod
    def setUpClass(cls):
        sm_path = import_ufo.find_ufo_path('sm')
        cls.full_model = import_ufo.import_full_model(sm_path)
        cls.default_model = import_ufo.import_model(sm_path)

    def test_flavour_scheme_options(self):
        """the three schemes only differ by the mass of the c and b quark"""

        categories = build_restrict_lib.get_generic_categories(self.full_model)
        option = get_option(categories, 'flavour scheme')
        self.assertNotEqual(option, None)
        self.assertEqual(option.labels, ['3F', '4F', '5F'])

        target = {}
        for label, rules in option.choices:
            target[label] = set((block.lower(), tuple(code))
                                for block, code, value in rules)
            # a mass scheme only puts parameters to zero
            self.assertEqual(set(value for block, code, value in rules) - set([0.]),
                             set())

        # u, d and s are massless in the sm UFO: nothing to restrict for 3F
        self.assertEqual(target['3F'], set())
        self.assertEqual(target['4F'], set([('mass', (4,)), ('yukawa', (4,))]))
        self.assertEqual(target['5F'], set([('mass', (4,)), ('yukawa', (4,)),
                                            ('mass', (5,)), ('yukawa', (5,))]))

    def test_lepton_scheme_options(self):
        """the massive leptons are taken from the heaviest one"""

        categories = build_restrict_lib.get_generic_categories(self.full_model)
        option = get_option(categories, 'nb of massive leptons')
        self.assertNotEqual(option, None)
        self.assertEqual(option.labels, ['0', '1', '2', '3'])

        target = {}
        for label, rules in option.choices:
            target[label] = set((block.lower(), tuple(code))
                                for block, code, value in rules)

        self.assertEqual(target['3'], set())
        self.assertEqual(target['2'], set([('mass', (11,)), ('yukawa', (11,))]))
        self.assertEqual(target['1'], set([('mass', (11,)), ('yukawa', (11,)),
                                           ('mass', (13,)), ('yukawa', (13,))]))
        # a massless particle can not decay: the tau width follows its mass
        self.assertEqual(target['0'], set([('mass', (11,)), ('yukawa', (11,)),
                                           ('mass', (13,)), ('yukawa', (13,)),
                                           ('mass', (15,)), ('yukawa', (15,)),
                                           ('decay', (15,))]))

    def test_default_follows_the_loaded_model(self):
        """the default of the options reproduces the model as loaded"""

        categories = build_restrict_lib.get_generic_categories(self.full_model,
                                                            self.default_model)
        # default sm: c massless, b massive / tau massive, e and mu massless
        self.assertEqual(get_option(categories, 'flavour scheme').status, '4F')
        self.assertEqual(get_option(categories, 'nb of massive leptons').status, '1')

        # on the full model everything is massive
        categories = build_restrict_lib.get_generic_categories(self.full_model)
        self.assertEqual(get_option(categories, 'flavour scheme').status, '3F')
        self.assertEqual(get_option(categories, 'nb of massive leptons').status, '3')


#===============================================================================
# The options of the question
#===============================================================================
class TestChoiceOption(unittest.TestCase):
    """A customization option with more than two values"""

    def get_option(self):
        return build_restrict_lib.ChoiceOption('scheme',
                    [('a', [('MASS', [5], 0.0)]), ('b', []), ('c', [])], 'b')

    def test_status(self):
        option = self.get_option()
        self.assertEqual(option.status, 'b')
        option.next_status()
        self.assertEqual(option.status, 'c')
        option.next_status()
        self.assertEqual(option.status, 'a')
        option.set_status('b')
        self.assertEqual(option.status, 'b')
        self.assertRaises(ValueError, option.set_status, 'd')

    def test_get_rules(self):
        option = self.get_option()
        self.assertEqual(option.get_rules(), [])
        option.set_status('a')
        self.assertEqual(option.get_rules(), [('MASS', [5], 0.0)])

    def test_rule_get_rules(self):
        category = build_restrict_lib.Category('test')
        category.add_options(name='massless b', default=False,
                             rules=[('MASS', [5], 0.0), ('YUKAWA', [5], 0.0)])
        self.assertEqual([r for rule in category for r in rule.get_rules()], [])
        for rule in category:
            rule.status = True
        self.assertEqual([r for rule in category for r in rule.get_rules()],
                         [('mass', [5], 0.0), ('yukawa', [5], 0.0)])


#===============================================================================
# The restriction card built by customize_model
#===============================================================================
class TestCustomizeCard(unittest.TestCase):
    """The way customize_model fills the restriction card"""

    @classmethod
    def setUpClass(cls):
        sm_path = import_ufo.find_ufo_path('sm')
        cls.model = import_ufo.import_full_model(sm_path)
        out = io.StringIO()
        param_writer.ParamCardWriter(cls.model, out)
        cls.text = out.getvalue()

    def setUp(self):
        self.cmd = mg_interface.MadGraphCmd()
        self.card = check_param_card.ParamCard(self.text.split('\n'))
        self.externals = self.cmd.get_external_lhacode(self.model)

    def test_randomize_only_touches_dangerous_values(self):
        """0, 1 and duplicated values are the ones removed by the restriction"""

        before = dict(((block, tuple(param.lhacode)), param.value)
                      for block in self.card for param in self.card[block])
        self.cmd.randomize_param_card(self.card, self.externals)

        for block in self.card:
            for param in self.card[block]:
                key = (block, tuple(param.lhacode))
                old, new = before[key], param.value
                if key not in self.externals:
                    # informative entries of the card: never touched
                    self.assertEqual(old, new)
                elif old in (0., 1.):
                    if block == 'decay' and old == 0.:
                        self.assertEqual(new, 0.) # a massless particle can not decay
                    else:
                        self.assertNotEqual(new, old)
                        self.assertTrue(0 < new < 1)

        # no value of the card can be simplified by the restriction anymore
        values = [param.value for block in self.card
                  for param in self.card[block]
                  if (block, tuple(param.lhacode)) in self.externals
                  and not (block == 'decay' and param.value == 0.)]
        self.assertEqual(len(values), len(set(values)))
        self.assertFalse([v for v in values if v in (0., 1.)])

    def test_randomize_keeps_the_order_of_magnitude(self):
        """MZ must not be replaced by a O(1) value because of a duplicate"""

        self.card['mass'].get([23]).value = 91.188
        self.card['mass'].get([25]).value = 91.188
        self.cmd.randomize_param_card(self.card, self.externals)
        values = sorted([self.card['mass'].get([23]).value,
                         self.card['mass'].get([25]).value])
        self.assertNotEqual(values[0], values[1])
        self.assertEqual(values[0], 91.188)
        self.assertTrue(91.188 < values[1] < 2 * 91.188)

    def test_apply_rules(self):
        """the user choices are written in the card"""

        category = build_restrict_lib.Category('test')
        category.add_options(name='massless b', default=True,
                             rules=[('MASS', [5], 0.0), ('YUKAWA', [5], 0.0)])

        restricted = self.cmd.apply_customize_rules(self.card, [category],
                    set_zero=[('mass', (4,))], set_one=[('sminputs', (3,))],
                    identify=[(('yukawa', (6,)), ('mass', (6,)))])

        self.assertEqual(self.card['mass'].get([5]).value, 0.)
        self.assertEqual(self.card['yukawa'].get([5]).value, 0.)
        self.assertEqual(self.card['mass'].get([4]).value, 0.)
        self.assertEqual(self.card['sminputs'].get([3]).value, 1.)
        self.assertEqual(self.card['yukawa'].get([6]).value,
                         self.card['mass'].get([6]).value)
        self.assertEqual(restricted,
                         set([('mass', (5,)), ('yukawa', (5,)), ('mass', (4,)),
                              ('sminputs', (3,)), ('yukawa', (6,))]))

    def test_identify_chain_is_resolved(self):
        """'identify A B' + 'identify B C' has to make the three of them equal,
        whatever the order they were entered in."""

        A, B, C = ('mass', (4,)), ('mass', (5,)), ('mass', (6,))
        for chain in ([(A, B), (B, C)], [(B, C), (A, B)]):
            card = check_param_card.ParamCard(self.text.split('\n'))
            identify = mg_interface.MadGraphCmd.resolve_identify(chain)
            self.cmd.apply_customize_rules(card, [], [], [], identify)
            values = [card['mass'].get([pdg]).value for pdg in (4, 5, 6)]
            self.assertEqual(values[0], values[2])
            self.assertEqual(values[1], values[2])

    def test_identify_cycle_does_not_loop(self):
        """'identify A B' + 'identify B A' is degenerate but must terminate"""

        A, B = ('mass', (4,)), ('mass', (5,))
        identify = mg_interface.MadGraphCmd.resolve_identify([(A, B), (B, A)])
        card = check_param_card.ParamCard(self.text.split('\n'))
        self.cmd.apply_customize_rules(card, [], [], [], identify)
        self.assertEqual(card['mass'].get([4]).value, card['mass'].get([5]).value)

    def test_identify_follows_a_restricted_parameter(self):
        """'identify A B' with B set to zero does put A to zero as well"""

        self.cmd.apply_customize_rules(self.card, [], set_zero=[('mass', (5,))],
                    set_one=[], identify=[(('yukawa', (5,)), ('mass', (5,)))])
        self.assertEqual(self.card['yukawa'].get([5]).value, 0.)


#===============================================================================
# The options of the model itself
#===============================================================================
class TestModelCategories(unittest.TestCase):
    """The options of the build_restrict.py of the model are kept only if they
    do not conflict with the generic ones"""

    @classmethod
    def setUpClass(cls):
        sm_path = import_ufo.find_ufo_path('sm')
        cls.full_model = import_ufo.import_full_model(sm_path)
        cls.default_model = import_ufo.import_model(sm_path)

    def setUp(self):
        self.cmd = mg_interface.MadGraphCmd()

    def test_group_options(self):
        """a category is a flat list of rules: they have to be re-grouped"""

        category = build_restrict_lib.Category('test')
        category.add_options(name='one', default=True,
                             rules=[('MASS', [5], 0.0), ('YUKAWA', [5], 0.0)])
        category.add_options(name='two', default=True, rules=[('MASS', [4], 0.0)])

        options = self.cmd.group_options(category)
        self.assertEqual([len(o) for o in options], [2, 1])
        self.assertEqual([o[0].name for o in options], ['one', 'two'])

    def test_sm_options(self):
        """the mass options of the sm are superseded by the generic ones"""

        categories = self.cmd.get_customize_categories(self.full_model,
                                                       self.default_model)
        names = [option.name for category in categories for option in category
                                                             if option.first]
        self.assertTrue('flavour scheme' in names)
        self.assertTrue('nb of massive leptons' in names)
        # the only option of the sm which is not about a mass
        self.assertTrue('diagonal ckm' in names)
        for dropped in ['c mass = 0', 'b mass = 0', 'tau mass = 0',
                        'muon mass = 0', 'electron mass = 0']:
            self.assertFalse(dropped in names)


#===============================================================================
# The commands of the customize_model question
#===============================================================================
class TestAskforCustomize(unittest.TestCase):
    """The parameter/coupling modifications entered at the question"""

    @classmethod
    def setUpClass(cls):
        sm_path = import_ufo.find_ufo_path('sm')
        cls.full_model = import_ufo.import_full_model(sm_path)

    def setUp(self):
        self.cmd = mg_interface.MadGraphCmd()
        self.cmd._curr_model = self.full_model
        categories = self.cmd.get_customize_categories(self.full_model,
                                                       self.full_model)
        self.ask = mg_interface.AskforCustomize('', mother_interface=self.cmd,
                                                categories=categories)

    def test_set_zero_and_set_one(self):
        self.ask.do_set_zero('MB')
        self.ask.do_set_one('lamWS')
        self.assertEqual(self.ask.set_zero, [('MASS', (5,))])
        self.assertEqual(self.ask.set_one, [('Wolfenstein', (1,))])

        # the name is case insensitive
        self.ask.do_set_zero('mta')
        self.assertEqual(self.ask.set_zero, [('MASS', (5,)), ('MASS', (15,))])

        # an unknown (or internal) parameter is refused
        self.ask.do_set_zero('NotAParameter')
        self.ask.do_set_zero('ee') # internal
        self.assertEqual(self.ask.set_zero, [('MASS', (5,)), ('MASS', (15,))])

    def test_a_parameter_has_only_one_status(self):
        """the last command entered for a parameter is the one kept"""

        self.ask.do_set_zero('MB')
        self.ask.do_set_one('MB')
        self.assertEqual(self.ask.set_zero, [])
        self.assertEqual(self.ask.set_one, [('MASS', (5,))])

        self.ask.do_identify('MB MT')
        self.assertEqual(self.ask.set_one, [])
        self.assertEqual(self.ask.identify, [(('MASS', (5,)), ('MASS', (6,)))])

    def test_identify(self):
        self.ask.do_identify('ymtau MTA')
        self.assertEqual(self.ask.identify, [(('YUKAWA', (15,)), ('MASS', (15,)))])
        # a parameter can not be identified to itself
        self.ask.do_identify('MTA MTA')
        self.assertEqual(len(self.ask.identify), 1)
        # wrong number of arguments
        self.ask.do_identify('MTA')
        self.assertEqual(len(self.ask.identify), 1)

    def test_formula_and_coupling(self):
        self.ask.do_formula('MB = MT/2.')
        self.assertEqual(self.ask.new_formula, [('MB', 'MT/2.')])
        # entering it twice only keeps the last one
        self.ask.do_formula('MB = MT/3.')
        self.assertEqual(self.ask.new_formula, [('MB', 'MT/3.')])
        # a parameter can not be defined from itself
        self.ask.do_formula('MB = MB/3.')
        self.assertEqual(self.ask.new_formula, [('MB', 'MT/3.')])
        # an internal parameter can not be redefined that way
        self.ask.do_formula('ee = 0.3')
        self.assertEqual(self.ask.new_formula, [('MB', 'MT/3.')])

        self.ask.do_coupling('GC_1 = 2*ee')
        self.assertEqual(self.ask.new_coupling, [('GC_1', '2*ee')])
        self.ask.do_coupling('NotACoupling = 2*ee')
        self.assertEqual(self.ask.new_coupling, [('GC_1', '2*ee')])

    def test_clear(self):
        self.ask.do_set_zero('MB')
        self.ask.do_formula('MTA = MT/2.')
        self.ask.do_coupling('GC_1 = 2*ee')
        self.ask.do_clear('')
        self.assertEqual(self.ask.set_zero, [])
        self.assertEqual(self.ask.new_formula, [])
        self.assertEqual(self.ask.new_coupling, [])

    def test_set_of_a_choice_option(self):
        """'set flavourscheme 5F' is the scripted version of the question"""

        self.ask.do_set('flavourscheme 5F')
        option = get_option(self.ask.all_categories, 'flavour scheme')
        self.assertEqual(option.status, '5F')
        # an invalid value does not change anything
        self.ask.do_set('flavourscheme 6F')
        self.assertEqual(option.status, '5F')
        # and the boolean options still work
        self.ask.do_set('diagonalckm False')
        self.assertEqual(get_option(self.ask.all_categories, 'diagonal ckm').status,
                         False)

    def test_question_lists_the_modifications(self):
        self.ask.do_set_zero('MB')
        self.ask.do_identify('ymtau MTA')
        self.ask.do_coupling('GC_1 = 2*ee')
        question = self.ask.get_question()
        self.assertTrue('MB (MASS [5]) = 0' in question)
        self.assertTrue('ymtau (YUKAWA [15]) = MTA (MASS [15])' in question)
        self.assertTrue('GC_1 = 2*ee' in question)

    def test_answer_is_the_categories(self):
        """ask() returns the options, both in interactive and script mode"""

        self.assertEqual(self.ask.answer, self.ask.all_categories)


#===============================================================================
# The name asked for the new model written by the advanced options
#===============================================================================
class TestAskforModelName(unittest.TestCase):
    """A script which does not answer that question must not have its next
    command used as the name of the model."""

    def setUp(self):
        self.question = mg_interface.AskforModelName('name?', default='sm_custom')

    def test_a_name_is_accepted(self):
        self.assertEqual(
            self.question.special_check_answer_in_input_file('my_model', 'x'),
            'my_model')
        self.assertEqual(
            self.question.special_check_answer_in_input_file('  sm2  ', 'x'),
            'sm2')

    def test_a_command_is_refused(self):
        for line in ['generate p p > t t~', 'output MYDIR', 'sm-restriction',
                     'a/b', '']:
            self.assertEqual(
                self.question.special_check_answer_in_input_file(line, 'x'),
                None, '%s should not be taken as a model name' % line)


#===============================================================================
# customize_model --explain
#===============================================================================
class TestExplainRestriction(unittest.TestCase):
    """The attribution of each removal to one of the user choices"""

    def setUp(self):
        self.cmd = mg_interface.MadGraphCmd()
        self.card = check_param_card.ParamCard("""
Block mass
    4 0.0 # mc
    5 2.0 # mb
    6 2.0 # mt
   23 1.0 # mz
Block yukawa
    5 2.0 # ymb
DECAY 6 0.0 # wt
DECAY 23 0.0 # wz
""".split('\n'))
        self.externals = set([('mass', (4,)), ('mass', (5,)), ('mass', (6,)),
                              ('mass', (23,)), ('yukawa', (5,)),
                              ('decay', (6,)), ('decay', (23,))])

    def test_parameter_classes(self):
        """0/1 leave the card, and so do the duplicates of a same block"""

        dropped, fused = self.cmd.get_parameter_classes(self.card, self.externals)
        # MC = 0, MZ = 1 and the two zero widths become internal parameters
        self.assertEqual(dropped, set([('mass', (4,)), ('mass', (23,)),
                                       ('decay', (6,)), ('decay', (23,))]))
        # MB and MT share their value, ymb only shares it across blocks
        self.assertEqual(fused, set([('mass', (5,)), ('mass', (6,))]))

    def test_zero_widths_are_not_fused(self):
        """two particles with a zero width are not two identical parameters"""

        dropped, fused = self.cmd.get_parameter_classes(self.card, self.externals)
        self.assertFalse([k for k in fused if k[0] == 'decay'])
        # they are zero, so they do leave the card
        self.assertTrue(('decay', (6,)) in dropped)

    def test_only_the_external_parameters_are_considered(self):
        """the informative entries of a param_card are not model parameters"""

        dropped, fused = self.cmd.get_parameter_classes(self.card, set())
        self.assertEqual(dropped, set())
        self.assertEqual(fused, set())


class TestRestrictionGroups(unittest.TestCase):
    """The user choices, as the units --explain attributes a removal to"""

    def setUp(self):
        self.cmd = mg_interface.MadGraphCmd()
        self.category = build_restrict_lib.Category('test')
        self.category.add_options(name='massless b', default=True,
                             rules=[('MASS', [5], 0.0), ('YUKAWA', [5], 0.0)])
        self.category.add_options(name='not selected', default=False,
                             rules=[('MASS', [4], 0.0)])
        self.category.append(build_restrict_lib.ChoiceOption('scheme',
                    [('a', [('MASS', [6], 0.0)]), ('b', [])], 'a'))

    def test_groups(self):
        groups = self.cmd.get_restriction_groups([self.category],
                    set_zero=[('YUKAWA', (6,))], set_one=[],
                    identify=[(('MASS', (5,)), ('MASS', (6,)))],
                    lha2name={('YUKAWA', (6,)): 'ymt', ('MASS', (5,)): 'MB',
                              ('MASS', (6,)): 'MT'})
        labels = [label for label, keys in groups]
        # an option which is not selected has no rule, so it is not a group
        self.assertEqual(labels, ['massless b', 'scheme = a', 'set_zero ymt',
                                  'identify MB MT'])
        keys = dict(groups)
        # the rules of an option are grouped together
        self.assertEqual(keys['massless b'],
                         set([('mass', (5,)), ('yukawa', (5,))]))
        self.assertEqual(keys['scheme = a'], set([('mass', (6,))]))
        self.assertEqual(keys['set_zero ymt'], set([('yukawa', (6,))]))
