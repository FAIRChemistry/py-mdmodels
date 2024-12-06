#  -----------------------------------------------------------------------------
#   Copyright (c) 2024 Jan Range
#
#   Permission is hereby granted, free of charge, to any person obtaining a copy
#   of this software and associated documentation files (the "Software"), to deal
#   in the Software without restriction, including without limitation the rights
#   to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#   copies of the Software, and to permit persons to whom the Software is
#   furnished to do so, subject to the following conditions:
#  #
#   The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
#  #
#   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#   OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#   THE SOFTWARE.
#  -----------------------------------------------------------------------------
import os
from typing import Iterable

import rich
from instructor import OpenAISchema

from mdmodels import sql, DataModel
from mdmodels.llm import query_openai

if os.path.exists("test.db"):
    os.remove("test.db")

enzymeml = DataModel.from_github(
    repo="EnzymeML/dm-specifications",
    branch="dm-2",
    spec_path="specifications/dm.md",
)

models = sql.generate_sqlmodel(
    data_model=enzymeml,
    base_classes=[OpenAISchema],
)

db = sql.DatabaseConnector(database="test.db")
db.create_tables(models)

with db as session:
    # Query the model
    molecules = query_openai(
        response_model=Iterable[models.SmallMolecule],
        query="List all small molecules in the glycolysis and pentose phosphate pathway.",
        use_scaffold=False,
    )

    proteins = query_openai(
        response_model=Iterable[models.Protein],
        query="List all proteins/enzymes in the glycolysis and pentose phosphate pathway.",
        use_scaffold=False,
    )

    rich.print(molecules)
    rich.print(proteins)

    session.add_all([*molecules, *proteins])
