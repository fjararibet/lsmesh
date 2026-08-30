"""Tests for pure 2D pipeline transformations."""

from lsmesher.geometry_types import Edge, Point2D
from lsmesher.pipeline_2d import (
    _region_seed_candidates,
    build_2d_poly_geometry,
    close_2d_layer,
    collect_2d_attributes,
    compute_bottom_points_2d_from_layers,
    geometry_2d_to_poly_text,
    merge_2d_layers,
    simplify_2d_geometry,
)
from lsmesher.pipeline_types import Geometry2D, Layer2D
from lsmesher.validation import validate


def fixed_attribute_sampler(_layer, _previous, *, originally_closed):
    """Return a deterministic attribute point for pipeline tests."""
    assert isinstance(originally_closed, bool)
    return Point2D(0.5, 0.5)


def test_region_seeds_cover_disconnected_material_components():
    outer = Layer2D(
        points=(
            Point2D(-2, -1),
            Point2D(2, -1),
            Point2D(2, 1),
            Point2D(-2, 1),
        ),
        edges=(Edge(0, 1), Edge(1, 2), Edge(2, 3), Edge(3, 0)),
    )
    divider = Layer2D(
        points=(
            Point2D(-0.5, -1),
            Point2D(0.5, -1),
            Point2D(0.5, 1),
            Point2D(-0.5, 1),
        ),
        edges=(Edge(0, 1), Edge(1, 2), Edge(2, 3), Edge(3, 0)),
    )

    seeds = _region_seed_candidates(outer, divider, originally_closed=False)

    assert len(seeds) == 2
    assert {point.x < 0 for point in seeds} == {False, True}


def test_compute_bottom_points_from_layers():
    """Bottom points span all layers and sit below the minimum y."""
    layers = (
        Layer2D(
            points=(Point2D(0.0, 0.0), Point2D(2.0, 4.0)),
            edges=(Edge(0, 1),),
        ),
        Layer2D(
            points=(Point2D(-1.0, 1.0), Point2D(3.0, 2.0)),
            edges=(Edge(0, 1),),
        ),
    )

    leftmost, rightmost = compute_bottom_points_2d_from_layers(layers)

    assert leftmost == Point2D(-1.0, -0.4)
    assert rightmost == Point2D(3.0, -0.4)


def test_close_2d_layer_leaves_closed_layer_unchanged():
    """Already closed layers are returned unchanged."""
    layer = Layer2D(
        points=(
            Point2D(0.0, 0.0),
            Point2D(1.0, 0.0),
            Point2D(1.0, 1.0),
            Point2D(0.0, 1.0),
        ),
        edges=(Edge(0, 1), Edge(1, 2), Edge(2, 3), Edge(3, 0)),
    )

    result = close_2d_layer(
        layer,
        leftmost_point=Point2D(0.0, -0.1),
        rightmost_point=Point2D(1.0, -0.1),
    )

    assert result == layer


def test_close_2d_layer_adds_bottom_connection_to_open_layer():
    """Open layers receive two bottom points and three closure edges."""
    layer = Layer2D(
        points=(Point2D(0.0, 0.0), Point2D(1.0, 1.0)),
        edges=(Edge(0, 1),),
    )

    result = close_2d_layer(
        layer,
        leftmost_point=Point2D(0.0, -0.1),
        rightmost_point=Point2D(1.0, -0.1),
    )

    assert result.points == (
        Point2D(0.0, 0.0),
        Point2D(1.0, 1.0),
        Point2D(0.0, -0.1),
        Point2D(1.0, -0.1),
    )
    assert result.edges == (Edge(0, 1), Edge(2, 3), Edge(2, 0), Edge(3, 1))


def test_collect_2d_attributes_uses_injected_sampler():
    """Attribute collection is deterministic when a sampler is injected."""
    layer = Layer2D(
        points=(
            Point2D(0.0, 0.0),
            Point2D(1.0, 0.0),
            Point2D(1.0, 1.0),
            Point2D(0.0, 1.0),
        ),
        edges=(Edge(0, 1), Edge(1, 2), Edge(2, 3), Edge(3, 0)),
    )

    attributes = collect_2d_attributes(
        (layer,),
        enabled=True,
        sampler=fixed_attribute_sampler,
    )

    assert attributes == (Point2D(0.5, 0.5),)


def test_merge_2d_layers_preserves_attributes():
    """Merged geometry carries caller-provided attribute points."""
    layer = Layer2D(
        points=(
            Point2D(0.0, 0.0),
            Point2D(1.0, 0.0),
            Point2D(0.0, 1.0),
        ),
        edges=(Edge(0, 1), Edge(1, 2), Edge(2, 0)),
    )

    result = merge_2d_layers((layer,), attributes=(Point2D(0.25, 0.25),))

    assert result.points == layer.points
    assert {edge.sorted() for edge in result.edges} == {
        edge.sorted() for edge in layer.edges
    }
    assert result.attributes == (Point2D(0.25, 0.25),)


def test_simplify_2d_geometry_removes_collinear_point():
    """Collinear points are removed from merged geometry."""
    geometry = Geometry2D(
        points=(
            Point2D(0.0, 0.0),
            Point2D(0.5, 0.0),
            Point2D(1.0, 0.0),
            Point2D(1.0, 1.0),
            Point2D(0.0, 1.0),
        ),
        edges=(Edge(0, 1), Edge(1, 2), Edge(2, 3), Edge(3, 4), Edge(4, 0)),
        attributes=(Point2D(0.25, 0.25),),
    )

    result = simplify_2d_geometry(geometry, epsilon=1e-6)

    assert Point2D(0.5, 0.0) not in result.points
    assert result.attributes == geometry.attributes


def test_simplify_2d_geometry_preserves_material_junctions():
    """Collinear degree-three vertices keep every material-interface branch."""
    geometry = Geometry2D(
        points=(
            Point2D(0.0, 0.0),
            Point2D(1.0, 0.0),
            Point2D(2.0, 0.0),
            Point2D(2.0, 2.0),
            Point2D(1.0, 2.0),
            Point2D(0.0, 2.0),
        ),
        edges=(
            Edge(0, 1),
            Edge(1, 2),
            Edge(2, 3),
            Edge(3, 4),
            Edge(4, 5),
            Edge(5, 0),
            Edge(1, 4),
        ),
    )

    result = simplify_2d_geometry(geometry, epsilon=1e-6)

    junction = result.points.index(Point2D(1.0, 0.0))
    assert sum(junction in edge.as_tuple() for edge in result.edges) == 3
    assert not validate(result).issues


def test_build_2d_poly_geometry_chains_steps():
    """The pure build function closes, samples, merges, and simplifies layers."""
    layer = Layer2D(
        points=(Point2D(0.0, 0.0), Point2D(1.0, 1.0)),
        edges=(Edge(0, 1),),
    )

    result = build_2d_poly_geometry(
        (layer,),
        epsilon=1e-6,
        detect_holes=True,
        sampler=fixed_attribute_sampler,
    )

    assert result.attributes
    assert len(result.points) >= 3
    assert len(result.edges) >= 3


def test_geometry_2d_to_poly_text_serializes_attributes():
    """POLY text serialization remains a pure final step."""
    geometry = Geometry2D(
        points=(Point2D(0.0, 0.0), Point2D(1.0, 0.0), Point2D(0.0, 1.0)),
        edges=(Edge(0, 1), Edge(1, 2), Edge(2, 0)),
        attributes=(Point2D(0.25, 0.25),),
    )

    result = geometry_2d_to_poly_text(geometry)

    assert result.splitlines()[0] == "3 2 0 0"
    assert "1 0.25 0.25 1 -1" in result


def test_geometry_2d_to_poly_text_preserves_explicit_material_ids():
    geometry = Geometry2D(
        points=(Point2D(0.0, 0.0), Point2D(1.0, 0.0), Point2D(0.0, 1.0)),
        edges=(Edge(0, 1), Edge(1, 2), Edge(2, 0)),
        attributes=(Point2D(0.2, 0.2), Point2D(0.3, 0.3)),
        attribute_ids=(10, 10),
    )

    result = geometry_2d_to_poly_text(geometry)

    assert "1 0.2 0.2 10 -1" in result
    assert "2 0.3 0.3 10 -1" in result
