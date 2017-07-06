from __future__ import division, unicode_literals, print_function

import itertools
import re
from collections import namedtuple

import numpy as np
from matminer.descriptors.base import AbstractFeaturizer
from matminer.descriptors.data import magpie_data
from matminer.descriptors.utils import get_holder_mean
from pymatgen import Element, Composition
from pymatgen.core.periodic_table import get_el_sp
from pymatgen.core.units import Unit

__author__ = 'Jimin Chen, Logan Ward, Saurabh Bajaj, Anubhav jain, Kiran Mathew'


class StoichiometricAttribute(AbstractFeaturizer):
    """
    Class to calculate stoichiometric attributes.

    Generates: Lp norm-based stoichiometric attribute.

    Args:
        p_list (list of ints): list of norms to calculate
    """

    def __init__(self, p_list=None):
        if p_list is None:
            self.p_list = [0, 2, 3, 5, 7, 10]
        else:
            self.p_list = p_list

    def featurize(self, comp):
        el_amt = comp.get_el_amt_dict()

        p_norms = [0] * len(self.p_list)
        n_atoms = sum(el_amt.values())

        for i in range(len(self.p_list)):
            if self.p_list[i] < 0:
                raise ValueError("p-norm not defined for p < 0")
            if self.p_list[i] == 0:
                p_norms[i] = len(el_amt.values())
            else:
                for j in el_amt:
                    p_norms[i] += (el_amt[j] / n_atoms) ** self.p_list[i]
                p_norms[i] = p_norms[i] ** (1.0 / self.p_list[i])

        return p_norms

    def generate_labels(self):
        labels = []
        for p in self.p_list:
            labels.append("%d-norm" % p)
        return labels


class ElementalAttribute(AbstractFeaturizer):
    """
    Class to calculate elemental property attributes.

    Generates: list representation with min, max, range, mean,  average deviation, and
        mode of descriptors

    Args:
        attributes (list of strings): List of elemental properties to use
    """

    def __init__(self, attributes=None):
        if attributes is None:
            self.attributes = ["Number", "MendeleevNumber", "AtomicWeight", "MeltingT", "Column",
                               "Row", "CovalentRadius", "Electronegativity",
                               "NsValence", "NpValence", "NdValence", "NfValence", "NValance",
                               "NsUnfilled", "NpUnfilled", "NdUnfilled", "NfUnfilled", "NUnfilled",
                               "GSvolume_pa", "GSbandgap", "GSmagmom", "SpaceGroupNumber"]
        else:
            self.attributes = attributes

    def featurize(self, comp):
        all_attributes = []

        for attr in self.attributes:
            elem_data = magpie_data.get_data(comp, attr)

            all_attributes.append(min(elem_data))
            all_attributes.append(max(elem_data))
            all_attributes.append(max(elem_data) - min(elem_data))

            prop_mean = sum(elem_data) / len(elem_data)
            all_attributes.append(prop_mean)
            all_attributes.append(sum(np.abs(np.subtract(elem_data, prop_mean))) / len(elem_data))
            all_attributes.append(max(set(elem_data), key=elem_data.count))

        return all_attributes

    def generate_labels(self):
        labels = []
        for attr in self.attributes:
            labels.append("Min %s" % attr)
            labels.append("Max %s" % attr)
            labels.append("Range %s" % attr)
            labels.append("Mean %s" % attr)
            labels.append("AbsDev %s" % attr)
            labels.append("Mode %s" % attr)
        return labels


class ValenceOrbitalAttribute(AbstractFeaturizer):
    """
    Class to calculate valence orbital attributes.
    Generate fraction of valence electrons in s, p, d, and f orbitals
    """

    def __init__(self):
        pass

    def featurize(self, comp):
        num_atoms = comp.num_atoms

        avg_total_valence = sum(magpie_data.get_data(comp, "NValance")) / num_atoms
        avg_s = sum(magpie_data.get_data(comp, "NsValence")) / num_atoms
        avg_p = sum(magpie_data.get_data(comp, "NpValence")) / num_atoms
        avg_d = sum(magpie_data.get_data(comp, "NdValence")) / num_atoms
        avg_f = sum(magpie_data.get_data(comp, "NfValence")) / num_atoms

        Fs = avg_s / avg_total_valence
        Fp = avg_p / avg_total_valence
        Fd = avg_d / avg_total_valence
        Ff = avg_f / avg_total_valence

        return list((Fs, Fp, Fd, Ff))

    def generate_labels(self):
        orbitals = ["s", "p", "d", "f"]
        labels = []
        for orb in orbitals:
            labels.append("Frac %s Valence Electrons" % orb)

        return labels


class IonicAttribute(AbstractFeaturizer):
    """
    Class to calculate ionic property attributes.

    Generates: [ cpd_possible (boolean value indicating if a neutral ionic compound is possible),
                 max_ionic_char (float value indicating maximum ionic character between two atoms),
                 avg_ionic_char (Average ionic character ]
    """

    def __init__(self):
        pass

    def featurize(self, comp):
        el_amt = comp.get_el_amt_dict()
        elements = list(el_amt.keys())
        values = list(el_amt.values())

        if len(elements) < 2:  # Single element
            cpd_possible = True
            max_ionic_char = 0
            avg_ionic_char = 0
        else:
            # Get magpie data for each element
            all_ox_states = magpie_data.get_data(comp, "OxidationStates")
            all_elec = magpie_data.get_data(comp, "Electronegativity")
            ox_states = []
            elec = []

            for i in range(1, len(values) + 1):
                ind = int(sum(values[:i]) - 1)
                ox_states.append(all_ox_states[ind])
                elec.append(all_elec[ind])

            # Determine if neutral compound is possible
            cpd_possible = False
            ox_sets = itertools.product(*ox_states)
            for ox in ox_sets:
                if np.dot(ox, values) == 0:
                    cpd_possible = True
                    break

                    # Ionic character attributes
            atom_pairs = itertools.combinations(range(len(elements)), 2)
            el_frac = list(np.divide(values, sum(values)))

            ionic_char = []
            avg_ionic_char = 0

            for pair in atom_pairs:
                XA = elec[pair[0]]
                XB = elec[pair[1]]
                ionic_char.append(1.0 - np.exp(-0.25 * (XA - XB) ** 2))
                avg_ionic_char += el_frac[pair[0]] * el_frac[pair[1]] * ionic_char[-1]

            max_ionic_char = np.max(ionic_char)

        return list((cpd_possible, max_ionic_char, avg_ionic_char))

    def generate_labels(self):
        labels = ["compound possible", "Max Ionic Char", "Avg Ionic Char"]
        return labels


def get_pymatgen_descriptor(composition, property_name):
    """
    Get descriptor data for elements in a compound from pymatgen.

    Args:
        composition (str/Composition): Either pymatgen Composition object or string formula,
            eg: "NaCl", "Na+1Cl-1", "Fe2+3O3-2" or "Fe2 +3 O3 -2"
            Notes:
                 - For 'ionic_radii' property, the Composition object must be made of oxidation
                    state decorated Specie objects not the plain Element objects.
                    eg.  fe2o3 = Composition({Specie("Fe", 3): 2, Specie("O", -2): 3})
                 - For string formula, the oxidation state sign(+ or -) must be specified explicitly.
                    eg.  "Fe2+3O3-2"

        property_name (str): pymatgen element attribute name, as defined in the Element class at
            http://pymatgen.org/_modules/pymatgen/core/periodic_table.html

    Returns:
        (list) of values containing descriptor floats for each atom in the compound(sorted by the
            electronegativity of the contituent atoms)

    """
    eldata = []
    # what are these named tuples for? not used or returned! -KM
    eldata_tup_lst = []
    eldata_tup = namedtuple('eldata_tup', 'element propname propvalue propunit amt')

    oxidation_states = {}
    if isinstance(composition, Composition):
        # check whether the composition is composed of oxidation state decorates species (not just plain Elements)
        if hasattr(composition.elements[0], "oxi_state"):
            oxidation_states = dict([(str(sp.element), sp.oxi_state) for sp in composition.elements])
        el_amt_dict = composition.get_el_amt_dict()
    # string
    else:
        comp, oxidation_states = get_composition_oxidation_state(composition)
        el_amt_dict = comp.get_el_amt_dict()

    symbols = sorted(el_amt_dict.keys(), key=lambda sym: get_el_sp(sym).X)

    for el_sym in symbols:

        element = Element(el_sym)
        property_value = None
        property_units = None

        try:
            p = getattr(element, property_name)
        except AttributeError:
            print("{} attribute missing".format(property_name))
            raise

        if p is not None:
            if property_name in ['ionic_radii']:
                if oxidation_states:
                    property_value = element.ionic_radii[oxidation_states[el_sym]]
                    property_units = Unit("ang")
                else:
                    raise ValueError("oxidation state not given for {}; It does not yield a unique "
                                     "number per Element".format(property_name))
            else:
                property_value = float(p)

            # units are None for these pymatgen descriptors
            # todo: there seem to be a lot more unitless descriptors which are not listed here... -Alex D
            if property_name not in ['X', 'Z', 'group', 'row', 'number', 'mendeleev_no', 'ionic_radii']:
                property_units = p.unit

        # Make a named tuple out of all the available information
        eldata_tup_lst.append(eldata_tup(element=el_sym, propname=property_name, propvalue=property_value,
                                         propunit=property_units, amt=el_amt_dict[el_sym]))

        # Add descriptor values, one for each atom in the compound
        for i in range(int(el_amt_dict[el_sym])):
            eldata.append(property_value)

    return eldata


def get_composition_oxidation_state(formula):
    """
    Returns the composition and oxidation states from the given formula.
    Formula examples: "NaCl", "Na+1Cl-1",   "Fe2+3O3-2" or "Fe2 +3 O3 -2"

    Args:
        formula (str):

    Returns:
        pymatgen.core.composition.Composition, dict of oxidation states as strings

    """
    oxidation_states_dict = {}
    non_alphabets = re.split('[a-z]+', formula, flags=re.IGNORECASE)
    if not non_alphabets:
        return Composition(formula), oxidation_states_dict
    oxidation_states = []
    for na in non_alphabets:
        s = na.strip()
        if s != "" and ("+" in s or "-" in s):
            digits = re.split('[+-]+', s)
            sign_tmp = re.split('\d+', s)
            sign = [x.strip() for x in sign_tmp if x.strip() != ""]
            oxidation_states.append("{}{}".format(sign[-1], digits[-1].strip()))
    if not oxidation_states:
        return Composition(formula), oxidation_states_dict
    formula_plain = []
    before, after = tuple(formula.split(oxidation_states[0], 1))
    formula_plain.append(before)
    for oxs in oxidation_states[1:]:
        before, after = tuple(after.split(oxs, 1))
        formula_plain.append(before)
    for i, g in enumerate(formula_plain):
        el = re.split("\d", g.strip())[0]
        oxidation_states_dict[str(Element(el))] = int(oxidation_states[i])
    return Composition("".join(formula_plain)), oxidation_states_dict


if __name__ == '__main__':

    import pandas as pd

    descriptors = ['atomic_mass', 'X', 'Z', 'thermal_conductivity', 'melting_point',
                   'coefficient_of_linear_thermal_expansion']

    for desc in descriptors:
        print(get_pymatgen_descriptor('LiFePO4', desc))
    print(magpie_data.get_data('LiFePO4', 'AtomicVolume'))
    print(magpie_data.get_data('LiFePO4', 'Density'))
    print(get_holder_mean([1, 2, 3, 4], 0))

    training_set = pd.DataFrame({"composition": ["Fe2O3"]})
    print("WARD NPJ ATTRIBUTES")
    print("Stoichiometric attributes")
    p_list = [0, 2, 3, 5, 7, 9]
    print(StoichiometricAttribute().featurize_all(training_set))
    print("Elemental property attributes")
    print(ElementalAttribute().featurize_all(training_set))
    print("Valence Orbital Attributes")
    print(ValenceOrbitalAttribute().featurize_all(training_set))
    print("Ionic attributes")
    print(IonicAttribute().featurize_all(training_set))