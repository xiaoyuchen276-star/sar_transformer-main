function audit_rgpi_author(root)
% Re-run the public author package on real H/S 128x128 scientific arrays.
expdir = fullfile(root, 'output', 'fig3_iceye_paris_20261109', 'seven_methods', 'rgpi');
addpath(fullfile(expdir, 'author_reference'));
outdir = fullfile(expdir, 'audit_20261114');
p = load(fullfile(outdir, 'author_probe.mat'));
results = repmat(struct('region', '', 'method', '', 'looks', 0, ...
    'author_identity', 0, 'author_filtered', 0, 'author_filtered_text', '', ...
    'filtered_is_finite', true, 'drop', 0, 'seconds', 0), 0, 1);
for region = 1:2
    baseline_grd = RGPI(p.GRD(:, :, region), p.GRD(:, :, region), 5, 9);
    baseline_slc = RGPI(p.projected_SLC(:, :, region), p.projected_SLC(:, :, region), p.slc_looks, 9);
    for method = 1:numel(p.method_names)
        if strcmp(p.method_names{method}, 'MERLIN')
            noisy = p.projected_SLC(:, :, region);
            looks = p.slc_looks;
            identity = baseline_slc;
        else
            noisy = p.GRD(:, :, region);
            looks = 5;
            identity = baseline_grd;
        end
        start = tic;
        filtered = RGPI(noisy, p.outputs(:, :, method, region), looks, 9);
        item = struct('region', p.region_names{region}, 'method', p.method_names{method}, ...
            'looks', looks, 'author_identity', identity, 'author_filtered', filtered, ...
            'author_filtered_text', sprintf('%.17g', filtered), ...
            'filtered_is_finite', isfinite(filtered), 'drop', identity-filtered, 'seconds', toc(start));
        results(end+1) = item; %#ok<AGROW>
        fprintf('%s %s: identity %.10f, filtered %.10f, drop %.10f\n', ...
            item.region, item.method, identity, filtered, item.drop);
    end
end
f = fopen(fullfile(outdir, 'author_probe.json'), 'w');
fwrite(f, jsonencode(results, 'PrettyPrint', true), 'char');
fclose(f);
end
