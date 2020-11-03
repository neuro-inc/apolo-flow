[comment]: # (Please do not modify this file)
[comment]: # (Put you comments to changelog.d and it will be moved to changelog in next release)

[comment]: # (Clear the text on make release for canceling the release)

[comment]: # (towncrier release notes start)

Neuro_Flow 20.11.3 (2020-11-03)
===============================

Features
--------


- Added validation of `outputs.needs` in batch actions. ([#163](https://github.com/neuro-inc/neuro-flow/issues/163))

- Store a JSON with live jobs configuration on every run job start. ([#170](https://github.com/neuro-inc/neuro-flow/issues/170))

- Implement ``lower()`` and ``upper()`` expression functions, e.g.  ``ref: image:${{ lower(flow.project_id) }}:v1.0`` ([#174](https://github.com/neuro-inc/neuro-flow/issues/174))


Bugfixes
--------


- Don't raise an error in `neuro-flow run` if the remote folder for the project already exists ([#184](https://github.com/neuro-inc/neuro-flow/issues/184))


Neuro_Flow 20.10.26 (2020-10-26)
================================

Features
--------


- Improve inspect command: sort output by task creation time, add columns with task start and task finish times. ([#156](https://github.com/neuro-inc/neuro-flow/issues/156))


Bugfixes
--------


- Fix variable substitution for printed text for bake cancellation ([#152](https://github.com/neuro-inc/neuro-flow/issues/152))

- Add forgotten restart command ([#160](https://github.com/neuro-inc/neuro-flow/issues/160))


Neuro_Flow 20.10.21 (2020-10-21)
================================

Features
--------


- Sort bakes by creation time. ([#147](https://github.com/neuro-inc/neuro-flow/issues/147))

- Support pass_config: true YAML option for task/job ([#151](https://github.com/neuro-inc/neuro-flow/issues/151))


Bugfixes
--------


- Ignore hidden files and folders (e.g. .cache) when getting the list of bakes ([#146](https://github.com/neuro-inc/neuro-flow/issues/146))


Neuro_Flow 20.10.19 (2020-10-19)
================================

Features
--------


- Added `--show-traceback` option. ([#134](https://github.com/neuro-inc/neuro-flow/issues/134))

- Tune a message about bake starting ([#135](https://github.com/neuro-inc/neuro-flow/issues/135))


Bugfixes
--------


- Fix noisy error report for `neuro kill ALL` command. ([#136](https://github.com/neuro-inc/neuro-flow/issues/136))

- Fix invariant by saving both started and finished records for cached task ([#139](https://github.com/neuro-inc/neuro-flow/issues/139))


Neuro_Flow 20.10.16 (2020-10-16)
================================

Features
--------


- Added --param option to `neuro-flow bake` command that allows to pass arguments to `params` section
  of the config file. ([#128](https://github.com/neuro-inc/neuro-flow/issues/128))

- Added --param option to `neuro-flow run` command that allows to pass arguments to `param` section
  of the job in config file. ([#132](https://github.com/neuro-inc/neuro-flow/issues/132))

- Added `upload()` function to re-upload volumes just before starting job in live mode. ([#133](https://github.com/neuro-inc/neuro-flow/issues/133))


Neuro_Flow 20.10.14 (2020-10-14)
================================

No significant changes.


Neuro_Flow 20.10.12 (2020-10-12)
================================

Bugfixes
--------


- Fix inspect command when there is a started but not finished action ([#122](https://github.com/neuro-inc/neuro-flow/issues/122))

- Fixed not marking cached task as done ([#123](https://github.com/neuro-inc/neuro-flow/issues/123))
