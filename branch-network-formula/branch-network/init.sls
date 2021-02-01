{% set branch_network_setup = salt['pillar.get']('branch_network') %}
{% set nic = salt['pillar.get']('branch_network:nic') %}

{%- if salt['pillar.get']('branch_network:dedicated_NIC') %}
restart_{{ nic }}:
  cmd.run:
    - names:
      - ifdown {{ nic }}
      - ifup {{ nic }}

/etc/sysconfig/network/ifcfg-{{ nic }}:
  file.managed:
    - source: salt://branch-network/files/ifcfg.template
    - user: root
    - group: root
    - mode: 644
    - template: jinja
    - onchanges_in:
      - cmd: restart_{{ nic }}
{%- endif %}

# Firewall configuration
{%- if salt['pillar.get']('branch_network:configure_firewall') %}
  {%- if salt['grains.get']('os_family') == 'Suse' %}
    {%- if salt['grains.get']('osfullname') == 'SLES' and salt['grains.get']('osmajorrelease')|int() == 12 %}
      {%- include 'branch-network/files/susefirewall.jinja' with context %}
    {%- else %}
      {%- include 'branch-network/files/firewalld.jinja' with context %}
    {%- endif %}
  {%- else %}
unsupported:
  test.fail_without_changes:
    - name: Branch Network Formula firewall setting is supported only on SUSE-based distributions.
  {%- endif %}
{%- endif %}

{%- if branch_network_setup.forwarder == "bind" %}
{# netconfig update fails if /etc/named.d directory does not exists and bind forwarder is used
   this directory is provided by named itself, installation of which is provided by bind formula
   however in case user does not want to use provided formulas, lets just create the directory here #}

named_dir:
  file.directory:
    - name: /etc/named.d
    - mode: 755
    - require_in:
      - cmd: netconfig_update
{%- endif %}

netconfig_update:
  cmd.run:
    - name: netconfig update

configure_forwarder:
  sysconfig.options_set:
    - name: /etc/sysconfig/network/config
    - options:
        NETCONFIG_DNS_FORWARDER: "{{ branch_network_setup.forwarder }}"
    - onchanges_in:
      - cmd: netconfig_update

configure_forwarder_fallback:
  sysconfig.options_set:
    - name: /etc/sysconfig/network/config
    - options:
        NETCONFIG_DNS_FORWARDER_FALLBACK: "{{ "yes" if branch_network_setup.forwarder_fallback else "no" }}"
    - onchanges_in:
      - cmd: netconfig_update

server_directory_setup:
  file.directory:
    - user:  {{ branch_network_setup.srv_directory_user }}
    - name:  {{ branch_network_setup.srv_directory }}
    - group: {{ branch_network_setup.srv_directory_group }}
    - mode:  755
    - makedirs: True
    - require:
        - user: server_directory_setup
  user.present:
    - name: {{ branch_network_setup.srv_directory_user }}
    - createhome: False
    - groups: 
        - {{ branch_network_setup.srv_directory_group }}
    - require:
        - group: server_directory_setup
  group.present:
    - name: {{ branch_network_setup.srv_directory_group }}

{% for service in [ 'ftp', 'tftp' ] %}
add_{{service}}_to_saltboot_group:
  group.present:
    - addusers:
      - {{service}}
    - name: {{ branch_network_setup.srv_directory_group }}
    - require:
      - group: server_directory_setup
      - user: add_{{service}}_to_saltboot_group
  user.present:
    - name: {{service}}
    - createhome: False
    - home: {{ branch_network_setup.srv_directory }}
    - require:
      - file: server_directory_setup
{% endfor %}

/etc/apache2/conf.d/susemanager-retail.conf:
  file.managed:
    - source: salt://branch-network/files/susemanager-retail.conf.template
    - user: root
    - group: root
    - mode: 644
    - template: jinja

apache2:
  service.running:
    - watch:
      - file: /etc/apache2/conf.d/susemanager-retail.conf

{{ branch_network_setup.srv_directory }}/defaults:
  file.managed:
    - source: salt://branch-network/files/defaults.template
    - user: root
    - group: root
    - mode: 644
    - template: jinja
