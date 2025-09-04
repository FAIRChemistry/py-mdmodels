//! This file contains Rust struct definitions with serde serialization.
//!
//! WARNING: This is an auto-generated file.
//! Do not edit directly - any changes will be overwritten.

use derive_builder::Builder;
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

//
// Type definitions
//
/// This object represents a chemical project and serves as the top-level
/// container for managing various aspects of a research project. It
/// organizes the project's title, associated molecules, reactions,
/// and experiments, providing a structured overview of the entire
/// chemical workflow.
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, Builder, Default)]
#[allow(non_snake_case)]
pub struct ChemicalProject {
    /// The name/title of the project.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    #[builder(default, setter(into))]
    pub title: Option<String>,

    /// The molecules used in the project.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    #[builder(default, setter(into, each(name = "to_molecules")))]
    pub molecules: Vec<Molecule>,

    /// The reactions in the project.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    #[builder(default, setter(into, each(name = "to_reactions")))]
    pub reactions: Vec<Reaction>,

    /// The experiments in the project.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    #[builder(default, setter(into, each(name = "to_experiments")))]
    pub experiments: Vec<Experiment>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, Builder, Default)]
#[allow(non_snake_case)]
pub struct Molecule {
    /// The identifier of the molecule.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    #[builder(default, setter(into))]
    pub id: Option<String>,

    /// The name of the molecule.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    #[builder(default = ""Lel".to_string().into()", setter(into))]
    pub name: Option<String>,

    /// The formula of the molecule.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    #[builder(default, setter(into))]
    pub formula: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, Builder, Default)]
#[allow(non_snake_case)]
pub struct Experiment {
    /// The identifier of the experiment.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    #[builder(default, setter(into))]
    pub id: Option<String>,

    /// The initial concentrations of the molecules in the experiment.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    #[builder(default, setter(into, each(name = "to_initial_concentrations")))]
    pub initial_concentrations: Vec<Concentration>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, Builder, Default)]
#[allow(non_snake_case)]
pub struct Concentration {
    /// The identifier of the molecule.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    #[builder(default, setter(into))]
    pub molecule_id: Option<String>,

    /// The concentration of the molecule.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    #[builder(default, setter(into))]
    pub value: Option<number>,

    /// The unit of the concentration.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    #[builder(default, setter(into))]
    pub unit: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, Builder, Default)]
#[allow(non_snake_case)]
pub struct Reaction {
    /// The identifier of the reaction.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    #[builder(default, setter(into))]
    pub id: Option<String>,

    /// The name of the reaction.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    #[builder(default, setter(into))]
    pub name: Option<String>,

    /// The reactants of the reaction.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    #[builder(default, setter(into, each(name = "to_educts")))]
    pub educts: Vec<Molecule>,

    /// The products of the reaction.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    #[builder(default, setter(into, each(name = "to_products")))]
    pub products: Vec<Molecule>,
}

#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema, Builder, Default)]
#[allow(non_snake_case)]
pub struct Element {
    /// The identifier of the molecule.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    #[builder(default, setter(into))]
    pub molecule_id: Option<String>,

    /// The stoichiometry of the reactant.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    #[builder(default, setter(into))]
    pub stoichiometry: Option<number>,
}