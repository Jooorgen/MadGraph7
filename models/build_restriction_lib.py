################################################################################
#
# Copyright (c) 2012 The MadGraph7 Development team and Contributors
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


class Rule(object):
    """ """
    
    def __init__(self, name, default, data,first=True, inverted_display=False):
        """ """
        self.name = name
        self.default=default
        self.status=default
        self.lhablock = data[0].lower()
        self.lhaid = data[1]
        self.value = data[2]
        self.first = first
        if inverted_display:
            self.display = lambda x: not x
        else:
            self.display = lambda x: x

    def get_rules(self):
        """the (lhablock, lhacode, value) to write in the restriction card"""

        if self.status:
            return [(self.lhablock, self.lhaid, self.value)]
        return []


class ChoiceOption(object):
    """An option with more than two -mutually exclusive- values (a Rule is
    the True/False case). choices is a list of (label, rules) where rules is
    the list of (lhablock, lhacode, value) to apply for that label."""

    # a ChoiceOption is not split over several entries (unlike Rule) so it is
    # always the entry displayed/toggled by the customize_model question
    first = True

    def __init__(self, name, choices, default, description=None):

        self.name = name
        self.choices = [(str(label), rules) for (label, rules) in choices]
        self.labels = [label for (label, rules) in self.choices]
        default = str(default)
        assert default in self.labels
        self.default = default
        self.status = default
        self.description = description

    def display(self, status):
        return status

    def set_status(self, value):
        """set the option to one of its allowed values"""

        value = str(value)
        if value not in self.labels:
            raise ValueError('%s is not a valid value for \'%s\'. Valid values are: %s'
                             % (value, self.name, ', '.join(self.labels)))
        self.status = value

    def next_status(self):
        """cycle to the next allowed value (interactive toggle)"""

        self.status = self.labels[(self.labels.index(self.status) + 1) % len(self.labels)]

    def get_rules(self):
        """the (lhablock, lhacode, value) to write in the restriction card"""

        for label, rules in self.choices:
            if label == self.status:
                return rules
        return []


class Category(list):
    """A container for the different rules"""
    
    def __init__(self, name, *args, **opt):
        """store a title for those restriction category"""
        
        self.name = name
        list.__init__(self, *args, **opt)
        
    def add_options(self, name='', default='', inverted_display=False, rules=[]):
        first=True
        for arg in rules:
            current_rule = Rule(name, default, arg, first, inverted_display) 
            self.append(current_rule)
            first=False


        
        
        


#===============================================================================
# Generic (model independent) customization options
#===============================================================================
# Those options are proposed for every model (on top of the model specific
# options defined in the build_restrict.py of the model -if any-). They are
# built from the content of the model itself: an option is proposed only if
# the associated particle/parameter is present (and external) in the model.

LIGHT_QUARKS = [1, 2, 3]   # d, u, s: massless in all the flavour schemes
HEAVY_QUARKS = [4, 5]      # c, b
LEPTONS = [15, 13, 11]     # tau, mu, e: ordered from the heaviest


def get_external_parameters(model):
    """return the list of the external parameters of the model"""

    try:
        return model['parameters'][('external',)]
    except (KeyError, TypeError):
        return []


def get_mass_rules(model, pdgs):
    """return the list of (lhablock, lhacode, 0.0) needed to set to zero the
    mass -and the associated width/yukawa- of all the particles of pdgs.
    Only the parameters which are external in model are returned."""

    externals = get_external_parameters(model)
    by_name = dict((param.name, param) for param in externals)
    particle_dict = model.get('particle_dict')

    rules = []
    done = set()
    for pdg in pdgs:
        particle = particle_dict.get(pdg, None)
        if particle is None:
            continue
        param = by_name.get(particle.get('mass'), None)
        if param is None:
            continue # already massless (or internal -> can not be restricted)
        key = (param.lhablock.lower(), tuple(param.lhacode))
        if key not in done:
            done.add(key)
            rules.append((param.lhablock, list(param.lhacode), 0.0))
        # a massless particle can not decay
        param = by_name.get(particle.get('width'), None)
        if param is not None:
            key = (param.lhablock.lower(), tuple(param.lhacode))
            if key not in done:
                done.add(key)
                rules.append((param.lhablock, list(param.lhacode), 0.0))

    # the yukawa couplings are not attached to a particle, so they have to be
    # looked for via their lhacode
    for param in externals:
        if param.lhablock.upper() != 'YUKAWA' or len(param.lhacode) != 1:
            continue
        if param.lhacode[0] not in pdgs:
            continue
        key = (param.lhablock.lower(), tuple(param.lhacode))
        if key not in done:
            done.add(key)
            rules.append((param.lhablock, list(param.lhacode), 0.0))

    return rules


def is_massive(model, pdg):
    """check if the particle pdg is massive in model (False if not present)"""

    particle = model.get('particle_dict').get(pdg, None)
    if particle is None:
        return False
    if particle.get('mass').lower() == 'zero':
        return False
    value = dict.get(model, 'parameter_dict', {})
    if particle.get('mass') in value:
        return bool(abs(complex(value[particle.get('mass')])))
    return True


def get_flavour_scheme_option(model, reference):
    """the 3F/4F/5F choice for the quarks. model is the model to restrict
    (no restriction applied), reference is the model as currently loaded by
    the user and is only used to define the default value of the option."""

    choices = []
    for nf in [3, 4, 5]:
        massless = [pdg for pdg in LIGHT_QUARKS + HEAVY_QUARKS if pdg <= nf]
        choices.append(('%dF' % nf, get_mass_rules(model, massless)))

    # nothing can be changed in this model: do not propose the option
    if not any(rules for label, rules in choices):
        return None

    # default: reproduce the scheme of the model as currently loaded
    if not is_massive(reference, 5) and not is_massive(reference, 4):
        default = '5F'
    elif not is_massive(reference, 4):
        default = '4F'
    else:
        default = '3F'

    return ChoiceOption('flavour scheme', choices, default,
              description='3F: c and b massive, 4F: b massive, 5F: none of them.'
                          ' u, d and s are massless in all the schemes')


def get_lepton_scheme_option(model, reference):
    """the number of massive leptons (0 to 3). Massive leptons are taken from
    the heaviest one: 1 -> tau, 2 -> tau and mu, 3 -> tau, mu and e."""

    choices = []
    for nb in [0, 1, 2, 3]:
        massless = LEPTONS[nb:]
        choices.append(('%d' % nb, get_mass_rules(model, massless)))

    if not any(rules for label, rules in choices):
        return None

    default = '%d' % len([pdg for pdg in LEPTONS if is_massive(reference, pdg)])

    return ChoiceOption('nb of massive leptons', choices, default,
                        description='0: all massless, 1: tau, 2: tau mu,'
                                    ' 3: tau mu e')


def get_generic_categories(model, reference=None):
    """return the list of the categories proposed for any model.
    model is the (unrestricted) model on which the restriction is applied,
    reference is the model as currently loaded by the user (used to define
    the default value of the options)."""

    if reference is None:
        reference = model

    category = Category('mass scheme')
    for option in [get_flavour_scheme_option(model, reference),
                   get_lepton_scheme_option(model, reference)]:
        if option is not None:
            category.append(option)

    if not category:
        return []
    return [category]


def get_rules_target(option):
    """return the set of (lhablock, lhacode) that an option can modify"""

    out = set()
    if isinstance(option, ChoiceOption):
        rules = sum([r for label, r in option.choices], [])
    else:
        rules = [(option.lhablock, option.lhaid, option.value)]
    for lhablock, lhacode, value in rules:
        out.add((lhablock.lower(), tuple(lhacode)))
    return out
