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

from enum import Enum
from mdmodels_core import Templates as RSTemplates  # type: ignore


class Templates(Enum):
    """Templates enum corresponding to RSTemplate"""

    # XML Schema
    XML_SCHEMA = RSTemplates.XmlSchema

    # Markdown
    MARKDOWN = RSTemplates.Markdown

    # Compact Markdown
    COMPACT_MARKDOWN = RSTemplates.CompactMarkdown

    # SHACL
    SHACL = RSTemplates.Shacl

    # JSON Schema
    JSON_SCHEMA = RSTemplates.JsonSchema

    # JSON Schema All
    JSON_SCHEMA_ALL = RSTemplates.JsonSchemaAll

    # SHACL
    SHEX = RSTemplates.Shex

    # Python Dataclass
    PYTHON_DATACLASS = RSTemplates.PythonDataclass

    # Python Pydantic XML
    PYTHON_PYDANTIC_XML = RSTemplates.PythonPydanticXML

    # Python Pydantic
    PYTHON_PYDANTIC = RSTemplates.PythonPydantic

    # MkDocs
    MKDOCS = RSTemplates.MkDocs

    # Internal
    INTERNAL = RSTemplates.Internal

    # Typescript (io-ts)
    TYPESCRIPT = RSTemplates.Typescript

    # Typescript (Zod)
    TYPESCRIPT_ZOD = RSTemplates.TypescriptZod

    # Rust
    RUST = RSTemplates.Rust

    # Protobuf
    PROTOBUF = RSTemplates.Protobuf

    # Graphql
    GRAPHQL = RSTemplates.Graphql

    # Golang
    GOLANG = RSTemplates.Golang

    # Linkml
    LINKML = RSTemplates.Linkml

    # Julia
    JULIA = RSTemplates.Julia

    # Mermaid class diagram
    MERMAID = RSTemplates.Mermaid
