import logging
log = logging.getLogger(__name__)

def _get_bundle_delta(rootdir, image_data, images):
    deltas = []
    for base_image_name, base_image_data in image_data.get('sync', {}).get('bundle_delta', {}).items():
        for base_image_version, delta_data in base_image_data.items():
            deltas.append((int(delta_data.get('size', 0)), base_image_name, base_image_version, delta_data))

    deltas = sorted(deltas, key = lambda x: x[0]) # sort by delta size, try shorter first

    for size, base_image_name, base_image_data, delta_data in deltas:
        base_image_data = images.get(base_image_name, {}).get(base_image_version)
        if not base_image_data:
           continue
        name = base_image_data['filename']
        local_path = rootdir + '/' + base_image_data['sync'].get('local_path')
        local_file = local_path + '/' + name
        if __salt__['file.file_exists'](local_file):
            ret = {'source': local_file}
            ret.update(delta_data)
            return ret

    return None

def _apply_bundle_delta(bundle_delta, tmpdir):
    delta = __salt__['cp.get_url'](bundle_delta.get('url'))

    res = __salt__['cmd.run_all']("xdelta3 -d -s {} {} {}" . format(bundle_delta['source'], delta, tmpdir + '/bundle.tar'))
    if res['retcode'] != 0:
        return None
    return tmpdir + '/bundle.tar'

def _download_bundle(image_data):
    if 'bundle_url' not in image_data['sync']:
        return None
    return __salt__['cp.get_url'](image_data['sync']['bundle_url'])

def image_synced(name, rootdir, image_data):
    ret = {
        'name': name,
        'changes': {},
        'result': True,
        'comment': '',
        'pchanges': {},
        }

    images = __pillar__.get('images', {})

    name = image_data['filename']
    local_path = rootdir + '/' + image_data['sync'].get('local_path')
    local_file = local_path + '/' + name
    image_hash = image_data.get('compressed_hash') or image_data['hash']

    parsed_hash = __salt__['file.get_source_sum'](source_hash=image_hash)
    have_sum = __salt__['file.get_sum'](local_file, parsed_hash['hash_type'])

    if (have_sum == parsed_hash['hsum']):
        ret['comment'] = "Image hash OK"
        return ret

    bundle = None
    temp_dir = None
    bundle_delta = _get_bundle_delta(rootdir, image_data, images)
    if bundle_delta:
        temp_dir = __salt__['temp.dir']()
        bundle = _apply_bundle_delta(bundle_delta, temp_dir)
    if not bundle:
        bundle = _download_bundle(image_data)

    if bundle:
       ret = __states__['archive.extracted'](name=local_path, source=bundle, makedirs=True, overwrite=True, enforce_toplevel=False)
       __salt__['cmd.run_all']("chmod -R a+r '{}'" . format(local_path))

       if temp_dir:
           __salt__['file.remove'](temp_dir)

       __salt__['file.remove'](bundle)

       return ret

    ret = __states__['file.managed'](name=local_file, source=image_data['sync']['url'], source_hash=image_hash, makedirs=True, force=True)
    return ret


