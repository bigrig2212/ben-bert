# -*- coding: utf-8 -*-
"""Bert - Question - Clustering

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1Pg9htpoW2g4KRFVxJniYVrXGg3vPPwBD

Using BERT to cluster questions
"""

# Commented out IPython magic to ensure Python compatibility.
from typing import Iterable, Tuple, List, Dict, Any, Union
from collections import OrderedDict

import argparse

import numpy as np
import pandas as pd
import tensorflow as tf
import plotly.graph_objects as go

from time import time
from pathlib import Path
from requests import Response, post
from tensorboard.plugins import projector

from sklearn.cluster import KMeans
from sklearn.manifold import TSNE

WORK_DIR = Path(__file__).resolve().parent
LOGS_DIR = WORK_DIR / "logs"

LOGS_DIR.mkdir(parents=True, exist_ok=True)

""" ------------------------------ Functions ------------------------------- """


def parse_args():
    """
    Parses arguments.

    Returns:

    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-f",
        "--file",
        type=Path,
        required=True,
        help="Filepath of the .csv input file",
    )
    parser.add_argument(
        "-c",
        "--column",
        type=str,
        required=True,
        help="Column name or index to parse sentences from",
    )
    parser.add_argument(
        "-o",
        "--out",
        type=Path,
        default=LOGS_DIR,
        required=False,
        help="Path where to save results"
    )
    parser.add_argument(
        "-oc",
        "--out-csv",
        type=Path,
        default=None,
        required=False,
        help="Path where to save .csv"
    )
    parser.add_argument(
        "-oh",
        "--out-html",
        type=Path,
        default=None,
        required=False,
        help="Path where to save .html"
    )
    parser.add_argument(
        "-r",
        "--rows",
        type=int,
        default=None,
        required=False,
        help="Num of rows to process [default=None] - all rows processed"
    )
    parser.add_argument(
        "-b",
        "--batch-size",
        type=int,
        default=1024,
        required=False,
        help="Batch size value for batch-wise processing"
    )
    parser.add_argument(
        "-d",
        "--dimensions",
        type=int,
        default=3,
        required=False,
        help="Number of output dimensions for T-SNE"
    )
    parser.add_argument(
        "-p",
        "--perplexity",
        type=int,
        default=25,
        required=False,
        help="Perplexity parameter for T-SNE"
    )
    parser.add_argument(
        "-l",
        "--learning-rate",
        type=int,
        default=10,
        required=False,
        help="Learning rate parameter for T-SNE"
    )
    parser.add_argument(
        "-i",
        "--iterations",
        type=int,
        default=500,
        required=False,
        help="Num iterations parameter for T-SNE"
    )
    parser.add_argument(
        "-s",
        "--seed",
        type=int,
        default=42,
        required=False,
        help="Random state value"
    )
    parser.add_argument(
        "-q",
        "--clusters",
        type=int,
        default=20,
        required=False,
        help="Number of clusters for KMeans"
    )
    parser.add_argument(
        "-t",
        "--tensorboard",
        type=Path,
        default=None,
        required=False,
        help="Path to save tensorboard to [default=None]"
    )

    args = parser.parse_args()
    return args


def post_request(sentences: List[str]) -> np.ndarray:
    """
    Function performs request to HTTP web service.

    curl --location --request POST 'http://35.232.149.171:8080/encode' \
    --header 'Content-Type: application/json' \
    --data-raw '{"id": 123, "is_tokenized": false, \
    "texts": ["what is up with you?", "How are you today?"]}'

    Args:
        sentences (List[str]): Sentences to send with shape (batch_size x n)

    Returns:
        (np.ndarray): Features extracted with shape (batch_size x feature_size)
    """
    url: str = "http://35.232.149.171:8080/encode"

    json: Dict = {
        "id": 123,
        "is_tokenized": False,
        "texts": sentences,
    }

    headers: Dict = {
        "Content-type": "application/json",
    }

    # perform request with sentences to receive features
    response: Response = post(url=url, headers=headers, json=json)
    response: Dict = response.json()

    if "result" in response:
        response: np.ndarray = np.asarray(response["result"])
    else:
        print("Unknown result")

    return response


def plot_with_tensorboard(
        logdir: Path,
        sentences: List[str],
        clusters: Union[List, np.ndarray],
        embeddings: Dict[str, np.ndarray],
):
    """
    Saves Tensorboard embeddings to projector.
    
    Args:
        logdir (Path): Directory where to save.
        sentences (List[str]): Sentences for metadata.
        embeddings (Dict[str, np.ndarray]): Embeddings to plot.
    """
    # Set up a logs directory, so Tensorboard knows where to look for files
    if not logdir.exists():
        logdir.mkdir(exist_ok=True, parents=True)

    # Save Labels separately on a line-by-line manner.
    with open(str(logdir / 'metadata.tsv'), "w") as f:
        f.write('Index\tSentence\tCluster\n')
        for i, (sentence, cluster) in enumerate(zip(sentences, clusters)):
            f.write(f"{i}\t{sentence}\t{cluster}\n")

    # Set up config
    config = projector.ProjectorConfig()
    variables = {}
    for name, embedding in embeddings.items():
        # Save the weights we want to analyse as a variable. Note that the first
        # value represents any unknown word, which is not in the metadata, so
        # we will remove that value.
        variable = tf.Variable(embedding, name=name)
        # Create a checkpoint from embedding, the filename and key are
        # name of the tensor.
        variables = {**variables, name: variable}

        embedding = config.embeddings.add()
        # The name of the tensor will be suffixed by `/.ATTRIBUTES/VARIABLE_VALUE`
        embedding.tensor_name = f"{name}/.ATTRIBUTES/VARIABLE_VALUE"
        embedding.metadata_path = "metadata.tsv"

    checkpoint = tf.train.Checkpoint(**variables)
    checkpoint.save(str(logdir / f"embeddings.ckpt"))
    projector.visualize_embeddings(str(logdir), config)


def plot_with_plotly(
        title: str,
        sentences: List[str],
        embeddings: np.ndarray,
        clusters: np.ndarray = None,
        out: Path = None
):
    """
    Plots one graph with plotly. 
    
    Args:
        sentences (List[str]): Sentences for metadata.
        embeddings (Tuple[str, np.ndarray]): Names and embeddings to plot.
    """
    length = len(embeddings)

    # if clusters were not defined, randomize colors for them
    if clusters is None:
        clusters = np.random.randn(length)

    if NUM_DIMS == 2:
        fig = go.Figure(data=go.Scattergl(
            x=embeddings[:, 0],
            y=embeddings[:, 1],
            text=sentences,
            name=title,
            mode='markers',
            marker=dict(
                color=clusters,
                colorscale='Viridis',
                line_width=1
            )
        ))
    else:
        fig = go.Figure(data=[go.Scatter3d(
            x=embeddings[:, 0],
            y=embeddings[:, 1],
            z=embeddings[:, 2],
            text=sentences,
            name=title,
            mode='markers',
            marker=dict(
                color=clusters,
                colorscale='Viridis',
                line_width=1
            ))
        ])

    # change sizes of layout and put the title

    if out is not None:
        fig.update_layout(height=1200, width=1600, title_text=title)
        fig.write_html(str(out))
    else:
        fig.update_layout(height=600, width=800, title_text=title)
        fig.show()


def batch(iterable: Iterable, batch_size: int = 1):
    """
    Performs batch-wise iteration.

    Args:
        iterable (Iterable): List or array to iterate
        batch_size (int): Batch size to iterate with

    Returns:
        (generator): Generator of size batch_size items
    """
    length = len(iterable)
    for index in range(0, length, batch_size):
        yield index, \
              iterable[index: min(index + batch_size, length)], \
              int(length/batch_size)


""" ------------------------------ Constants ------------------------------- """

args = parse_args()

DF_PATH: Path = args.file
COLUMN: str = args.column
NUM_ROWS_TO_USE: int = args.rows
BATCH_SIZE: int = args.batch_size
RANDOM_STATE: int = args.seed
NUM_DIMS: int = args.dimensions

""" ----------------------------- Data loading ----------------------------- """

# open CSV dataframe with all sentences
assert DF_PATH.exists(), f"`{DF_PATH}` file not found"
df: pd.DataFrame = pd.read_csv(filepath_or_buffer=DF_PATH)

print(f"Columns: {list(df.columns.values)}")

# extract question column from dataframe
# extract NUM_ROWS_TO_USE only to reduce time of the computations
columns = {v.lower().strip(): v for v in df.columns.values}
column = columns[COLUMN.lower().strip()]
num_sentences: int = len(df)

if NUM_ROWS_TO_USE is not None:
    if num_sentences < NUM_ROWS_TO_USE:
        print(f"Dataframe has less than {num_sentences} rows, "
              f"extracting all rows instead {NUM_ROWS_TO_USE} passed")
        NUM_ROWS_TO_USE = num_sentences
    else:
        num_sentences = NUM_ROWS_TO_USE

assert column in columns.values(), f"`{COLUMN}` column not found in .csv file"
data: pd.Series = df[column]
all_sentences: list = data.values.tolist()[:num_sentences]

print(f"Num of sentences extracted: {num_sentences}")

""" ------------------------- Features extraction -------------------------- """

# iterate over all questions and extract features
all_features = []
for i, questions, l in batch(all_sentences, batch_size=BATCH_SIZE):
    t0 = time()

    response = post_request(sentences=questions)
    all_features.extend(response)

    t1 = time()

    print(f"Batch processed within {t1 - t0:.2g} sec, "
          f"total ({i+1}/{l} batches processed)")

all_features = np.asarray(all_features)

print(f"Features matrix {all_features.shape} was built")

""" ------------------------------ Clustering ------------------------------ """

NUM_CLUSTERS = args.clusters

t0 = time()

# train KMeans algorithm with NUM_CLUSTERS
kmeans = KMeans(n_clusters=NUM_CLUSTERS, random_state=RANDOM_STATE)

# use that algorithm to get numbers of clusters for every feature
clusters = kmeans.fit_predict(all_features)

t1 = time()

print(f"Clustering done in {t1 - t0:.2g} sec")
print(f"Clusters {clusters.shape} was built")

""" ----------------------------- Tensorboard ------------------------------ """

out_tb: Path = args.tensorboard
if out_tb is not None:
    # save all original features to tensorboard
    original_features = {
        "original": all_features,
    }

    out_tb.mkdir(parents=True, exist_ok=True)

    plot_with_tensorboard(
        logdir=out_tb,
        sentences=all_sentences,
        embeddings=original_features,
        clusters=clusters
    )

""" -------------------------------- T-SNE --------------------------------- """

PERPLEXITY = args.perplexity
LEARNING_RATE = args.learning_rate
NUM_ITERATIONS = args.iterations

t0 = time()

# train T-SNE algorithm with parameters above
tsne = TSNE(n_components=NUM_DIMS, random_state=RANDOM_STATE,
            perplexity=PERPLEXITY, n_iter=NUM_ITERATIONS,
            learning_rate=LEARNING_RATE, init='random')

# use that algorithm to get reduced features
reduced_features = tsne.fit_transform(all_features)

t1 = time()

print(f"Done in {t1 - t0:.2g} sec")
print(f"Reduced features matrix {reduced_features.shape} was built")

""" ------------------------------- Plotly --------------------------------- """

out: Path = args.out

# prepare path for saving .html
out_html: Path = args.out_html

if out_html is None:
    out_html = out

if out_html.is_dir():
    out_html.mkdir(parents=True, exist_ok=True)
    out_html = out_html / "result.html"
else:
    out_html.parent.mkdir(parents=True, exist_ok=True)

# plotting reduced features along with their clusters with plotly
plot_with_plotly(
    title=f"Perplexity = {PERPLEXITY}, Num clusters = {NUM_CLUSTERS}",
    sentences=[f"{c}: {(q[:75] + '..') if len(q) > 75 else q}"
               for q, c in zip(all_sentences, clusters)],
    embeddings=reduced_features,
    clusters=clusters,
    out=out_html,
)
print(f"Plotly html saved to {out_html}")

""" --------------------------------- CSV ---------------------------------- """

# prepare path for saving .csv
out_csv: Path = args.out_csv
if out_csv is None:
    out_csv = out

if out_csv.is_dir():
    out_csv.mkdir(parents=True, exist_ok=True)
    out_csv = out_csv / "result.csv"
else:
    out_csv.parent.mkdir(parents=True, exist_ok=True)

if NUM_DIMS == 3:
    dict_to_save: OrderedDict = OrderedDict(**{
        # "show_id": all_show_numbers,
        "cluster_id": clusters,
        "x": reduced_features[:, 0],
        "y": reduced_features[:, 1],
        "z": reduced_features[:, 2],
        "sentence": all_sentences,
    })
else:
    dict_to_save: OrderedDict = OrderedDict(**{
        # "show_id": all_show_numbers,
        "cluster_id": clusters,
        "x": reduced_features[:, 0],
        "y": reduced_features[:, 1],
        "sentence": all_sentences,
    })

# saving to result.csv
df_to_save: pd.DataFrame = pd.DataFrame.from_dict(dict_to_save)
df_to_save.to_csv(out_csv)
print(f"Csv file saved to {out_csv}")
