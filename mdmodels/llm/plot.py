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
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from mdmodels import DataModel


class PlotTemplate(BaseModel):
    """
    A model representing a plot template.

    Attributes:
        title (str): The title of the plot.
        x_label (str): The label for the x-axis.
        y_label (str): The label for the y-axis.
        x_data_json_path (str): The JSON path to the x-axis data.
        y_data_json_path (str): The JSON path to the y-axis data.
    """

    title: str = Field(
        ...,
        description="The title of the plot.",
    )
    x_label: str = Field(
        ...,
        description="The label for the x-axis.",
    )
    y_label: str = Field(
        ...,
        description="The label for the y-axis.",
    )
    x_data_json_path: str = Field(
        ...,
        description="The JSON path to the x-axis data.",
    )
    y_data_json_path: str = Field(
        ...,
        description="The JSON path to the y-axis data.",
    )

    def plot(self, data: "Response"):
        """
        Plot the data using the template.

        Args:
            data (BaseModel): The data to plot.
        """
        import matplotlib.pyplot as plt

        if self.x_data_json_path is None or self.y_data_json_path is None:
            print(
                "x_data_json_path and y_data_json_path are required to plot the data."
            )
            return

        x_data = self.extract_data(data, self.x_data_json_path)
        y_data = self.extract_data(data, self.y_data_json_path)

        if not x_data:
            print(
                "Could not find data for x-axis or y-axis "
                f"in the provided JSON path {self.x_data_json_path}"
            )
            return

        if not y_data:
            print(
                "Could not find data for x-axis or y-axis "
                f"in the provided JSON path {self.y_data_json_path}"
            )
            return

        plt.plot(x_data, y_data)
        plt.xlabel(self.x_label)
        plt.ylabel(self.y_label)
        plt.title(self.title)

        plt.savefig(f"{self.title.lower().replace(' ', '_')}_plot.png")
        plt.show()

    @staticmethod
    def extract_data(data: DataModel, path: str) -> Any | None:
        """
        Extract data from the given JSON path.

        Args:
            data (BaseModel): The data to extract from.
            path (str): The JSON path to the data.

        Returns:
            Any: The extracted data.
        """

        if path.startswith("$.data"):
            path = path.replace("$.data", "$")

        try:
            return data.find(path)[0]
        except IndexError:
            return None
