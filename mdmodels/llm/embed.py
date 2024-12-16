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

import asyncio
from typing import Iterable
import numpy as np
from openai import OpenAI

from mdmodels.datamodel import DataModel


def embedding(
    dataset: DataModel | Iterable[DataModel] | str,
    model: str = "text-embedding-3-large",
    api_key: str | None = None,
    base_url: str | None = None,
) -> np.ndarray:
    """
    Embed a dataset using the specified model from OpenAI.

    This function takes a dataset, which can be a single DataModel instance or an iterable of DataModel instances,
    and generates embeddings for each data point using the specified model from OpenAI's API.

    Args:
        dataset (DataModel | Iterable[DataModel]): The dataset to embed. Can be a single DataModel instance or an iterable of DataModel instances.
        model (str, optional): The model to use for generating embeddings. Defaults to "text-embedding-3-large".
        api_key (str | None, optional): The API key for accessing OpenAI's API. If not provided, it will be fetched from the environment variable "OPENAI_API_KEY".
        base_url (str | None, optional): The base URL for the OpenAI API. Defaults to None.
    Returns:
        np.ndarray: A numpy array containing the embeddings for the dataset.

    Example:
        >>> from mdmodels.llm.embed import embed_dataset
        >>> embeddings = embedding(data, model="text-embedding-3-large", api_key="your_api_key")
        >>> print(embeddings)
        array([[0.1, 0.2, 0.3, ...]])
    """

    client = OpenAI(api_key=api_key, base_url=base_url)

    if not isinstance(dataset, list):
        dataset = [dataset]

    if not all(isinstance(dataset, str) for dataset in dataset):
        dataset = asyncio.run(
            asyncio.gather(*[_serialize_dataset(dataset) for dataset in dataset])
        )

    response = client.embeddings.create(
        input=dataset,
        model=model,
    )

    return np.array([data.embedding for data in response.data])


def _serialize_datasets(datasets: Iterable[DataModel]) -> list[str]:
    return [_serialize_dataset(dataset) for dataset in datasets]


async def _serialize_dataset(dataset: DataModel | Iterable[DataModel]) -> list[str]:
    return dataset.model_dump_json(exclude_none=True)
