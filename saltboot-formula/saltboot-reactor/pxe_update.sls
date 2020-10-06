# update pxe config
{% set minion_id = data['id'] %}
{% set minion_grains = data['data']['grains'] %}
{% set event_data = data['data'] %}

{% set branch_id = minion_grains.get('minion_id_prefix') %}
{% set terminal_entry_pillar = {
    'terminal_hwaddr_interfaces': minion_grains['hwaddr_interfaces'],
    'salt_device': event_data.get('salt_device'),
    'root': event_data.get('root'),
    'boot_image': event_data['boot_image'],
    'terminal_kernel_parameters': event_data.get('terminal_kernel_parameters', '')
} %}

handle_pxe_update_event:
  local.state.sls:
    - tgt: pxe:branch_id:{{ branch_id }}
    - tgt_type: pillar
    - args:
      - mods: pxe/terminal_entry
      - queue: True
      - pillar: {{ terminal_entry_pillar|yaml }}
