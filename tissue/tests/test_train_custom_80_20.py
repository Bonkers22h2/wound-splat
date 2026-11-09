from tissue.compare_models import make_folds
from tissue.train_custom_80_20 import select_training_fold


def test_selected_80_20_fold_matches_the_reported_comparison():
    pairs = [(f"image-{i}", f"mask-{i}") for i in range(110)]

    training, held_out = select_training_fold(pairs)

    assert len(training) == 88
    assert len(held_out) == 22
    assert held_out == make_folds(pairs)[0]
    assert set(training).isdisjoint(held_out)
    assert set(training) | set(held_out) == set(pairs)
