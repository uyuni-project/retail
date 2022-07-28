
support_packages:
  pkg.installed:
    - pkgs:
# Do not install xdelta3 on SLE12 based systems. It is not available there
{%- if (grains.get('osfullname') != 'SLES') or (grains.get('osmajorrelease')|int() != 12) %}
      - xdelta3
{%- endif %}
      - dosfstools

{%- set boot_images = pillar.get('boot_images', {}) %}
{%- set rootdir = pillar.get('branch_network', {'srv_directory':'/srv/saltboot'})['srv_directory'] %}
{%- set boot_dir = "boot" %}
{%- set whitelist = salt['pillar.get']('image-synchronize:whitelist', []) %}
{%- set branch_id = salt['pillar.get']('pxe:branch_id', "unknown") %}

{%- for arch_list, arch_suffix in [(['x86_64', 'i586', 'i686'], ''), (['aarch64'], '_arm64')] %}
{%- set boot_images_in_use = {} %}

{%- for image_id, image_version, image_data in salt['image_sync.filter_images'](whitelist, arch_list) %}
{%-     set name = image_data['filename'] %}
{%-     set local_path = rootdir + '/' + image_data['sync'].get('local_path') %}
{%-     set local_file = local_path + '/' + name %}
{%-     set hash = image_data.get('compressed_hash') or image_data['hash'] %}
{%-     do boot_images_in_use.update({image_data['boot_image']: True }) %}

{{ local_file }}:
  image_sync.image_synced:
    - rootdir: {{ rootdir }}
    - image_data: {{ image_data|yaml }}

# store synced images in grains
images:{{ image_id }}:{{ image_version }}:
  grains.present:
    - value: {{ image_data|yaml }}
    - force: True
  event.send:
    - name: suse/manager/image_synced
    - data:
        branch: {{ branch_id }}
        action: add
        image_name: {{ image_id }}
        image_version: {{ image_version }}
    - require:
        - image_sync: {{ local_file }}

{%- endfor %}

{%- for image_id, image_version, image_data in salt['image_sync.deleted_images'](arch_list) %}
{%-     set name = image_data['filename'] %}
{%-     set local_path_relative = image_data['sync'].get('local_path') %}
{%-     set local_path = rootdir + '/' + local_path_relative %}
{%-     set local_file = local_path + '/' + name %}

{%- if local_path_relative %}
{{ local_path }}:
  file.absent
{%- else %}
{{ local_file }}:
  file.absent
{%- endif %}

images:{{ image_id }}:{{ image_version }}:
  grains.absent:
    - destructive: true
    - force: true
  event.send:
    - name: suse/manager/image_synced
    - data:
        branch: {{ branch_id }}
        action: remove
        image_name: {{ image_id }}
        image_version: {{ image_version }}

{%- endfor %}


{%- set default_boot_image = salt['pillar.get']('image-synchronize:default_boot_image' + arch_suffix, 'default' + arch_suffix) %}
{%- if default_boot_image not in boot_images_in_use %}
{%-   if default_boot_image not in boot_images %}
{%-     if boot_images_in_use|length > 0 %}
{%-       set new_default_boot_image = salt['image_sync.get_default_boot_image'](boot_images_in_use.keys()) %}

default_boot_image_missing:
  test.show_notification:
    - text: Boot image {{ default_boot_image }} is not configured in pillar, using {{ new_default_boot_image }}

{%-       set default_boot_image = new_default_boot_image %}
{%-     endif %}
{%-   else %}
{%-     if boot_images[default_boot_image].get('sync', {}).get('kernel_url') %}
{%-       do boot_images_in_use.update({default_boot_image: True }) %}
{%-     else %}

default_boot_image_not_synced:
  test.show_notification:
    - text: Boot image {{ default_boot_image }} cant be synced standalone

{%-     endif %}
{%-   endif %}
{%- endif %}

{%- for boot_image_id in boot_images_in_use.keys() %}
{%-   set boot_image_data = boot_images[boot_image_id] %}
{%-   set local_path = rootdir + '/' + boot_dir + '/' + boot_image_data['sync']['local_path'] or '' %}
{%-   set local_path_relative = boot_image_data['sync']['local_path'] or '' %}
{%-   set kernel_name = boot_image_data['kernel']['filename'] %}
{%-   set kernel_hash = boot_image_data['kernel']['hash'] %}
{%-   set local_kernel_file = local_path + '/' + kernel_name %}
{%-   set local_kernel_file_relative = local_path_relative + '/' + kernel_name %}
{%-   set initrd_name = boot_image_data['initrd']['filename'] %}
{%-   set initrd_hash = boot_image_data['initrd']['hash'] %}
{%-   set local_initrd_file = local_path + '/' + initrd_name %}
{%-   set local_initrd_file_relative = local_path_relative + '/' + initrd_name %}

{{ local_path }}:
  file.directory:
    - makedirs: True

{%- if boot_image_data['sync']['kernel_link'] is defined %}
{{ local_kernel_file }}:
  file.symlink:
    - target: {{ boot_image_data['sync']['kernel_link'] }}
    - force: True
{%- endif %}

{%- if boot_image_data['sync']['initrd_link'] is defined %}
{{ local_initrd_file }}:
  file.symlink:
    - target: {{ boot_image_data['sync']['initrd_link'] }}
    - force: True
{%- endif %}

{%- if boot_image_data['sync']['kernel_url'] is defined %}
{{ local_kernel_file }}:
  file.managed:
    - source: {{ boot_image_data['sync']['kernel_url'] }}
    - source_hash: {{ kernel_hash }}
    - makedirs: True
{%- endif %}

{%- if boot_image_data['sync']['initrd_url'] is defined %}
{{ local_initrd_file }}:
  file.managed:
    - source: {{ boot_image_data['sync']['initrd_url'] }}
    - source_hash: {{ initrd_hash }}
    - makedirs: True
{%- endif %}

# store synced boot images in grains
boot_images:{{ boot_image_id }}:
  grains.present:
    - value: {{ boot_image_data|yaml }}
    - force: True

{%- if boot_image_id == default_boot_image %}
# symlinks for default boot image

{{ rootdir + '/' + boot_dir + '/initrd' + arch_suffix }}:
  file.symlink:
    - target: {{ local_initrd_file_relative }}
    - force: True

{%-   if arch_suffix == '' %}
#compatibility symlink
{{ rootdir + '/' + boot_dir + '/initrd.gz' }}:
  file.symlink:
    - target: initrd
    - force: True
{%-  endif %}

{{ rootdir + '/' + boot_dir + '/linux' + arch_suffix }}:
  file.symlink:
    - target: {{ local_kernel_file_relative }}
    - force: True

{%- endif %}
{%- endfor %}


{%- for boot_image_id, boot_image_data in salt['image_sync.deleted_boot_images'](boot_images_in_use, arch_list) %}
{%-   set local_path = rootdir + '/' + boot_dir + '/' + boot_image_data['sync']['local_path'] or '' %}
{%-   set local_path_relative = boot_image_data['sync']['local_path'] or '' %}
{%-   set kernel_name = boot_image_data['kernel']['filename'] %}
{%-   set local_kernel_file = local_path + '/' + kernel_name %}
{%-   set initrd_name = boot_image_data['initrd']['filename'] %}
{%-   set local_initrd_file = local_path + '/' + initrd_name %}

{%- if local_path_relative %}
{{ local_path }}:
  file.absent
{%- else %}
{{ local_kernel_file }}:
  file.absent

{{ local_initrd_file }}:
  file.absent

{%- endif %}

boot_images:{{ boot_image_id }}:
  grains.absent:
    - destructive: true
    - force: true

{%- endfor %}

{%- endfor %}

