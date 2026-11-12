function run_sarbm3d_tiles(project_root, experiment)
% Filter the fixed Paris GRD crop at its native grid with contextual tiles.
    package = fullfile(project_root, 'external', 'sarbm3d', 'SARBM3D_v10_win64');
    out = fullfile(experiment, 'runs', 'sarbm3d');
    if ~exist(out, 'dir'), mkdir(out); end
    input = load(fullfile(experiment, 'input.mat'), 'noisy');
    noisy = double(input.noisy);
    core = 512;
    halo = 64;
    looks = 5;
    [height, width] = size(noisy);
    assert(isequal(size(noisy), [3072,3072]));
    count = (height / core) * (width / core);
    pool = gcp('nocreate');
    if isempty(pool), pool = parpool('Processes', 6); end
    fprintf('SAR-BM3D: %d tiles, core %d, halo %d, L=%g\n', count, core, halo, looks);
    started = tic;
    parfor index = 1:count
        tile_path = fullfile(out, sprintf('tile_%02d.mat', index));
        if isfile(tile_path), continue; end
        addpath(package);
        setenv('PATH', [package, pathsep, getenv('PATH')]);
        row = floor((index-1)/(width/core))*core + 1;
        col = mod(index-1,width/core)*core + 1;
        r0 = max(1,row-halo); r1 = min(height,row+core-1+halo);
        c0 = max(1,col-halo); c1 = min(width,col+core-1+halo);
        amplitude = sqrt(noisy(r0:r1,c0:c1));
        restored = SARBM3D_v10(amplitude, looks);
        denoised = double(restored(row-r0+1:row-r0+core, col-c0+1:col-c0+core)).^2;
        assert(all(isfinite(denoised(:))));
        save_tile(tile_path, denoised);
        fprintf('SAR-BM3D tile %d/%d complete\n', index, count);
    end
    denoised = zeros(height, width);
    for index = 1:count
        row = floor((index-1)/(width/core))*core + 1;
        col = mod(index-1,width/core)*core + 1;
        tile = load(fullfile(out, sprintf('tile_%02d.mat',index)), 'denoised');
        denoised(row:row+core-1,col:col+core-1) = tile.denoised;
    end
    seconds = toc(started);
    save(fullfile(out, 'result.mat'), 'denoised', 'noisy', 'looks', 'core', 'halo', 'seconds', '-v7');
    fprintf('SAR-BM3D complete in %.1f seconds\n', seconds);
    delete(pool);
end

function save_tile(path, denoised)
    save(path, 'denoised', '-v7');
end
