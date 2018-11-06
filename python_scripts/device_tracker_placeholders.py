# Create placeholder device_tracker.meta entities at startup
hass.states.set('device_tracker.sussa', 'unknown', {
    'friendly_name': 'Sussa',
    'last_update_source': 'placeholder'
})

hass.states.set('device_tracker.erik', 'unknown', {
    'friendly_name': 'Erik',
    'last_update_source': 'placeholder'
})
