import subprocess
import json

import graphviz
from typer import Typer
from pathlib import Path

app = Typer()

def get_import_graph(root:Path, exclude:set[Path])->dict[Path, list[Path]]:
    raw = json.loads(subprocess.check_output(["ruff","analyze","graph", str(root)]))
    relative = {}
    absolute = root.resolve()
    for er, ees in raw.items():
        er_path = Path(er).relative_to(absolute)
        if any(er_path.is_relative_to(exclude_path) for exclude_path in exclude):
            continue

        relative[er_path] = [Path(ee).relative_to(absolute) for ee in ees]
    return relative

def build_dir_graphviz(import_graph:dict[Path, list[Path]])->graphviz.Digraph:
    graph = graphviz.Digraph()
    ids = {}

    def _get_id(name: Path) -> str:
        if name in ids:
            return ids[name]
        id_ = f"node_{len(ids)}"
        ids[name] = id_
        return id_

    all_dirs = set()
    for er, ees in import_graph.items():
        all_dirs.add(er.parent)
        all_dirs.update(ee.parent for ee in ees)

    for dir_ in all_dirs:
        graph.node(_get_id(dir_), graphviz.escape(str(dir_)))

    edges = set()
    for er, ees in import_graph.items():
        for ee in ees:
            edge = (_get_id(er.parent), _get_id(ee.parent))
            if edge in edges:
                continue
            edges.add(edge)
            graph.edge(*edge)

    return graph

def build_graphviz(import_graph: dict[Path, list[Path]], *, show_clusters:bool=False, only_crossing:bool=False) ->graphviz.Digraph:
    graph = graphviz.Digraph()
    ids = {}
    def _get_id(name:Path)->str:
        if name in ids:
            return ids[name]
        id_ = f"node_{len(ids)}"
        ids[name] = id_
        return id_

    clusters:dict[Path, graphviz.Digraph] = {Path("."):graph}
    def _get_cluster(name:Path)->graphviz.Digraph():
        if name in clusters:
            return clusters[name]
        cluster = graphviz.Digraph(name=f"cluster_{len(clusters)}")
        cluster.attr(label=graphviz.escape(str(name)))
        clusters[name] = cluster
        return cluster


    all_files = set()
    for er, ees in import_graph.items():
        if only_crossing and all(ee.parent == er.parent for ee in ees):
            continue
        all_files.add(er)
        all_files.update(ees)


    for file in sorted(all_files):
        if show_clusters:
            g = _get_cluster(file.parent)
        else:
            g = graph
        g.node(_get_id(file), graphviz.escape(str(file)))

    for er, ees in import_graph.items():
        for ee in ees:
            if only_crossing and er.parent == ee.parent:
                continue
            graph.edge(_get_id(er), _get_id(ee))

    if show_clusters:
        for path in sorted(clusters, reverse=True):
            if path == path.parent:
                continue
            _get_cluster(path.parent).subgraph(_get_cluster(path))

    return graph

@app.command()
def main(root:Path, out:Path, *, show_clusters:bool=True, only_crossing:bool=False, exclude:list[Path]|None=None, keep_dotfile:bool=False):
    exclude = exclude if exclude else set()
    import_graph = get_import_graph(root, exclude=exclude)
    graph = build_graphviz(import_graph, show_clusters=show_clusters, only_crossing=only_crossing)
    graph.format="svg"
    graph.render(out, cleanup=not keep_dotfile)
    dir_graph = build_dir_graphviz(import_graph)
    dir_graph.format="svg"
    dir_graph.render(out.with_suffix(".dirs"), cleanup=not keep_dotfile)


if __name__ == "__main__":
    app()