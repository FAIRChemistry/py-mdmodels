# This file contains Julia type definitions with JSON serialization.
#
# WARNING: This is an auto-generated file.
# Do not edit directly - any changes will be overwritten.

module BasicExample

using JSON3
using StructTypes

#=
  Type Definitions
  ---------------
  Main struct definitions with their fields and JSON serialization support.
=#


Base.@kwdef mutable struct Element
    """
    The identifier of the molecule.
    """
    molecule_id::Union{ String, Nothing} = nothing

    """
    The stoichiometry of the reactant.
    """
    stoichiometry::Union{ number, Nothing} = nothing

end

export Element


Base.@kwdef mutable struct Concentration
    """
    The identifier of the molecule.
    """
    molecule_id::Union{ String, Nothing} = nothing

    """
    The concentration of the molecule.
    """
    value::Union{ number, Nothing} = nothing

    """
    The unit of the concentration.
    """
    unit::Union{ String, Nothing} = nothing

end

export Concentration


Base.@kwdef mutable struct Experiment
    """
    The identifier of the experiment.
    """
    id::Union{ String, Nothing} = nothing

    """
    The initial concentrations of the molecules in the experiment.
    """
    initial_concentrations::Union{Vector{ Concentration }, Nothing} = nothing

end

export Experiment


Base.@kwdef mutable struct Molecule
    """
    The identifier of the molecule.
    """
    id::Union{ String, Nothing} = nothing

    """
    The name of the molecule.
    """
    name::Union{ String, Nothing} = nothing

    """
    The formula of the molecule.
    """
    formula::Union{ String, Nothing} = nothing

end

export Molecule


Base.@kwdef mutable struct Reaction
    """
    The identifier of the reaction.
    """
    id::Union{ String, Nothing} = nothing

    """
    The name of the reaction.
    """
    name::Union{ String, Nothing} = nothing

    """
    The reactants of the reaction.
    """
    educts::Union{Vector{ Molecule }, Nothing} = nothing

    """
    The products of the reaction.
    """
    products::Union{Vector{ Molecule }, Nothing} = nothing

end

export Reaction


"""
This object represents a chemical project and serves as the top-
level container for managing various aspects of a research project.
It organizes the project's title, associated molecules, reactions, and
experiments, providing a structured overview of the entire chemical
workflow.
"""
Base.@kwdef mutable struct ChemicalProject
    """
    The name/title of the project.
    """
    title::Union{ String, Nothing} = nothing

    """
    The molecules used in the project.
    """
    molecules::Union{Vector{ Molecule }, Nothing} = nothing

    """
    The reactions in the project.
    """
    reactions::Union{Vector{ Reaction }, Nothing} = nothing

    """
    The experiments in the project.
    """
    experiments::Union{Vector{ Experiment }, Nothing} = nothing

end

export ChemicalProject


end # module basic_example