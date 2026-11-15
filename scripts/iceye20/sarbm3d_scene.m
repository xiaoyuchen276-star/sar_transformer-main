function sarbm3d_scene(config_path)
% Native-grid SLC intensity inference. No metric calculation or image resizing.
    cfg = jsondecode(fileread(config_path));
    package = fullfile(cfg.project, 'external', 'sarbm3d', 'SARBM3D_v10_win64');
    assert(isfolder(package), 'Missing official SAR-BM3D package');
    assert(cfg.looks == 1);
    nr = ceil(cfg.height / cfg.core); nc = ceil(cfg.width / cfg.core);
    pool = gcp('nocreate');
    if isempty(pool), pool = parpool('Processes', cfg.workers); end
    parfor index = 1:(nr * nc)
        addpath(package);
        setenv('PATH', [package, pathsep, getenv('PATH')]);
        src = memmapfile(cfg.input, 'Offset', cfg.input_offset, 'Format', {'single', [cfg.width cfg.height], 'pixels'});
        dst = memmapfile(cfg.output, 'Offset', cfg.output_offset, 'Writable', true, 'Format', {'single', [cfg.width cfg.height], 'pixels'});
        row = floor((index - 1) / nc) * cfg.core + 1;
        col = mod(index - 1, nc) * cfg.core + 1;
        hh = min(cfg.core, cfg.height - row + 1); ww = min(cfg.core, cfg.width - col + 1);
        r0 = max(1, row - cfg.halo); r1 = min(cfg.height, row + hh - 1 + cfg.halo);
        c0 = max(1, col - cfg.halo); c1 = min(cfg.width, col + ww - 1 + cfg.halo);
        amplitude = sqrt(double(src.Data.pixels(c0:c1, r0:r1)'));
        % Pad tiny edge shapes to the method's minimum support if necessary.
        pad = max([64 64] - size(amplitude), 0);
        amplitude = padarray(amplitude, pad, 'symmetric', 'post');
        estimate = SARBM3D_v10(amplitude, cfg.looks);
        core = max(double(estimate(row-r0+1:row-r0+hh, col-c0+1:col-c0+ww)), 0).^2;
        assert(all(isfinite(core(:))), 'Nonfinite SAR-BM3D output');
        dst.Data.pixels(col:col+ww-1, row:row+hh-1) = single(core');
        if mod(index, 100) == 0, fprintf('SAR-BM3D %d/%d\n', index, nr*nc); end
    end
    delete(pool);
end
