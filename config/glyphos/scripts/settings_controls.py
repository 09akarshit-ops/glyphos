"""Identify the visible Settings layer for shared system window controls."""
SETTINGS={'glyphos-settings-app-max':'settings-app-max','glyphos-settings-app':'settings-app','glyphos-settings':'settings-window'}
def visible_settings(layers):
 namespaces={surface.get('namespace') for monitor in layers.values() for group in monitor.get('levels',{}).values() for surface in group}
 return next((name for namespace,name in SETTINGS.items() if namespace in namespaces),None)
