"""Validate the fixed head, eligibility and byte hashes of the 1.3 handoff."""
import hashlib
import math


CLASS_COUNT = 1498
ELIGIBLE_COUNT = 1491


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def validate(contract, labels, label_bytes, checkpoint_bytes=None):
    ids = [label['id'] for label in labels]
    if (len(ids) != CLASS_COUNT or len(set(ids)) != CLASS_COUNT
            or ids != sorted(ids) or contract['classCount'] != CLASS_COUNT):
        raise ValueError('Release requires the ordered 1,498-class head')
    eligible = {label['id'] for label in labels if label.get('confirmed', True)}
    declared = contract['confirmedEntryIDs']
    if (len(eligible) != ELIGIBLE_COUNT or len(declared) != ELIGIBLE_COUNT
            or set(declared) != eligible or 110126 in eligible):
        raise ValueError('Release requires exactly 1,491 eligible classes; Small Pumpkaboo remains suggestions-only')
    if contract['labelsSHA256'] != sha(label_bytes):
        raise ValueError('Release label bytes do not match their frozen SHA')
    if checkpoint_bytes is not None and contract['checkpointSHA256'] != sha(checkpoint_bytes):
        raise ValueError('Release checkpoint bytes do not match their frozen SHA')
    if contract['modelResource'] != 'NationalClassifier' or contract['inputSize'] != 224:
        raise ValueError('Unexpected app model input contract')
    for key in ('checkpointSHA256', 'labelsSHA256', 'trainingManifestSHA256'):
        value = contract.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError(f'Invalid release {key}')
    confidence, margin = contract['confidenceThreshold'], contract['logitMargin']
    if (not math.isfinite(confidence) or not .0 <= confidence <= 1.
            or not math.isfinite(margin) or margin < 0):
        raise ValueError('Invalid release acceptance thresholds')
