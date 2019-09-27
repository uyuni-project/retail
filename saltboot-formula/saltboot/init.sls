

{%- set partitioning = salt['pillar.get']('partitioning', {}) %}
{%- set images = salt['pillar.get']('images', {}) %}
{%- set boot_images = salt['pillar.get']('boot_images', {}) %}
{%- set initrd = salt['grains.get']('saltboot_initrd') %}

{% if initrd %}

# partition all disks
{% for disk_id, disk_data in partitioning.items() if disk_data['type'] == 'DISK' and disk_data.get('disklabel') != 'none' %}
{{ disk_id }}_partitioned:
  saltboot.disk_partitioned:
    - name: {{ disk_id }}
    - data: {{ disk_data|yaml }}
{% endfor %}

# create / assemble all RAIDs and eventually partition them
{% for disk_id, disk_data in partitioning.items() if disk_data['type'] == 'RAID' %}
{{ disk_id }}_created:
  saltboot.raid_created:
    - name: {{ disk_id }}
    - partitioning: {{ partitioning|yaml }}

{% if disk_data.get('disklabel') != 'none' %}
{{ disk_id }}_partitioned:
  saltboot.disk_partitioned:
    - name: {{ disk_id }}
    - data: {{ disk_data|yaml }}
    - require:
      - saltboot: {{ disk_id }}_created
{% endif %}
{% endfor %}

# format all partitions or deploy images
{% for disk_id, disk_data in partitioning.items() %}
# iterate over partitions or fall back to whole disk if no partitions exists
{% set todo_data = disk_data.get('partitions') %}
{% if disk_data.get('disklabel') == 'none': %}
{%   set todo_data = { '' : disk_data } %}
{% endif %}
{% for part_id, part_data in todo_data.items() %}
{% if 'image' in part_data %}
{{ disk_id + part_id }}_deployed:
  saltboot.image_deployed:
    - name: {{ disk_id + part_id }}
    - partitioning: {{ partitioning|yaml }}
    - images: {{ images|yaml }}
  {% if disk_data.get('disklabel') != 'none' %}
    - require:
      - saltboot: {{ disk_id }}_partitioned
  {% endif %}
  {% if disk_data['type'] == 'RAID' %}
    - require:
      - saltboot: {{ disk_id }}_created
  {% endif %}
    - require_in:
      - saltboot: saltboot_fstab
{% elif 'format' in part_data %}
{{ disk_id + part_id }}_formatted:
  saltboot.device_formatted:
    - name: {{ disk_id + part_id }}
    - partitioning: {{ partitioning|yaml }}
  {% if 'partitions' in disk_data %}
    - require:
      - saltboot: {{ disk_id }}_partitioned
  {% endif %}
  {% if disk_data['type'] == 'RAID' %}
    - require:
      - saltboot: {{ disk_id }}_created
  {% endif %}
    - require_in:
      - saltboot: saltboot_fstab
{% endif %}
{% endfor %}
{% endfor %}

{% if not partitioning %}
no_pillar:
  test.configurable_test_state:
    - name: no_pillar
    - changes: False
    - result: False
    - comment: partitioning pillar is missing

{% else %}

saltboot_fstab:
  saltboot.fstab_updated:
    - partitioning: {{ partitioning|yaml }}
    - images: {{ images|yaml }}
    - require_in:
      - saltboot: boot_system

boot_system:
  saltboot.verify_and_boot_system:
    - partitioning: {{ partitioning|yaml }}
    - images: {{ images|yaml }}
    - boot_images: {{ boot_images|yaml }}
    - action: {{ salt['pillar.get']('saltboot:kernel_action', 'kexec') }}

{% endif %}

{% endif %}
