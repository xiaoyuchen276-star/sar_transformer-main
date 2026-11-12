"""Check the unusual Paris H result against the authors' original test flow."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/sar2sar'))
import verify_original_parity as verification
import numpy as np
from PIL import Image


def main():
    scene=ROOT/'output/fig3_iceye_paris_20261109'
    out=scene/'seven_methods/sar2sar_validation'
    inputs=out/'input'
    reference_out=out/'official_reference'
    inputs.mkdir(parents=True,exist_ok=True)
    reference_out.mkdir(exist_ok=True)
    roi=json.loads((scene/'fig3_selection.json').read_text())['rois']['H']
    amplitude=np.asarray(Image.open(scene/'crops/fig3_view_amplitude.tif'),dtype=np.float32)
    amplitude=amplitude[roi['row_start']:roi['row_start']+384,roi['col_start']:roi['col_start']+384]
    np.save(inputs/'paris_H.npy',amplitude)
    package,provenance=verification.validate_official_package()
    verification.load_original('utils',package/'utils.py')
    verification.load_original('u_net',package/'u_net.py')
    model=verification.load_original('model',package/'model.py')
    tf=verification.tf
    config=tf.ConfigProto(device_count={'GPU':0},intra_op_parallelism_threads=2,inter_op_parallelism_threads=1)
    with tf.Graph().as_default(),tf.Session(config=config) as session:
        reference=model.denoiser(session)
        reference.test([str((inputs/'paris_H.npy').as_posix())],
                       str((package/'checkpoint').as_posix()),str(reference_out.as_posix()),
                       str(inputs.as_posix()),stride=64)
    expected=np.load(reference_out/'denoised_paris_H.npy')
    actual,execution=verification.infer(amplitude,package,stride=64,threads=2)
    np.testing.assert_allclose(actual,expected,rtol=2e-5,atol=1e-5)
    np.save(out/'saved_graph_amplitude.npy',actual)
    report={'passed':True,'input':'original ICEYE Paris H amplitude DN','shape':list(amplitude.shape),
            'source_commit':provenance['source_commit'],
            'reference':'authors u_net.py + model.denoiser.test + utils.py, original checkpoint',
            'reference_compatibility_changes':['TensorFlow imports -> compat.v1','unused regularizer -> None'],
            'bitwise_equal':bool(np.array_equal(actual,expected)),
            'maximum_absolute_amplitude_difference':float(np.max(np.abs(actual-expected))),
            'original_reference_output_ENL':float(np.mean(expected.astype(np.float64)**2)**2/np.var(expected.astype(np.float64)**2,ddof=1)),
            'execution':execution}
    (out/'verification.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
