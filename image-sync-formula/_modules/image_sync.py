import logging
log = logging.getLogger(__name__)


def _sort_images(image_list):
    res = []
    done = set()
    todo = set()

    for i in image_list:
        image_id, image_version, image_data = i
        todo.add((image_id, image_version))

    while True:
        changed = False
        for i in image_list:
            image_id, image_version, image_data = i
            if (image_id, image_version) in done:
                continue
            num_deltas = 0
            if __grains__.get('osfullname') != 'SLES' or __grains__.get('osmajorrelease') != 12:
                for dep_name, dep_versions in image_data.get('sync', {}).get('bundle_delta', {}).items():
                    for dep_version, dep_data in dep_versions.items():
                        if (dep_name, dep_version) not in todo:
                            continue # ignore unresolvable deltas
                        num_deltas += 1
                        if (dep_name, dep_version) in done:
                            res.append(i)
                            done.add((image_id, image_version))
                            changed = True
                            log.debug("Can use delta {} {} -> {} {}".format(dep_name, dep_version, image_id, image_version))
            if num_deltas == 0: # no deltas available
                res.append(i)
                done.add((image_id, image_version))
                changed = True
                log.debug("Base image without dependencies {} {}".format(image_id, image_version))
        if not changed:
            break

    for i in image_list: # put unresolvables and cycles at the end
        image_id, image_version, image_data = i
        if (image_id, image_version) in done:
            continue
        res.append(i)
        log.debug("Possible delta dependency cycle: {} {}".format(image_id, image_version))
    return res

def filter_images(whitelist = [], arch_list = ['x86_64', 'i586', 'i686']):
    images = __pillar__.get('images', {})
    res = []
    for image_id, image_versions in images.items():
        if whitelist and image_id not in whitelist:
            continue
        for image_version, image_data in image_versions.items():
            if 'filename' not in image_data:
                continue
            if image_data.get('arch') not in arch_list:
                continue
            res.append((image_id, image_version, image_data))

    res = _sort_images(res)

    return res


def deleted_images(arch_list = ['x86_64', 'i586', 'i686']):
    pillar_images = __pillar__.get('images', {})
    grains_images = __grains__.get('images', {})
    res = []
    for image_id, image_versions in grains_images.items():
        for image_version, image_data in image_versions.items():
            if image_data.get('arch') not in arch_list:
                continue
            if not pillar_images.get(image_id, {}).get(image_version, {}).get('filename'):
                res.append((image_id, image_version, image_data))
    return res


def deleted_boot_images(boot_images_in_use, arch_list = ['x86_64', 'i586', 'i686']):
    pillar_boot_images = __pillar__.get('boot_images', {})
    grains_boot_images = __grains__.get('boot_images', {})

    deleted_bundle_boot_images = []
    for image_id, image_version, image_data in deleted_images():
        boot_image_id = image_data.get('boot_image')

        if pillar_boot_images.get(boot_image_id, {}).get('sync', {}).get('kernel_link'):
            deleted_bundle_boot_images.append(boot_image_id)


    res = []
    for boot_image_id, boot_image_data in grains_boot_images.items():
        if boot_image_id in boot_images_in_use:
            continue
        if pillar_boot_images.get(boot_image_id, {}).get('arch') not in arch_list:
            continue
        if boot_image_id not in pillar_boot_images or boot_image_id in deleted_bundle_boot_images:
            res.append((boot_image_id, boot_image_data))
    return res
