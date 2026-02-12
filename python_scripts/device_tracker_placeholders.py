# Create placeholder device_tracker.meta entities at startup
hass.states.set('person.sussa', 'unknown', {
    'friendly_name': 'Sussa',
    'last_update_source': 'placeholder'
})

hass.states.set('person.erik', 'unknown', {
    'friendly_name': 'Erik',
    'last_update_source': 'placeholder'
})
