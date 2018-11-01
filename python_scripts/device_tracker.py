# Get Data from Automation Trigger
triggeredEntity = data.get('entity_id')
metatrackerName = "device_tracker." + data.get('meta_entity')

# Get new state
newState = hass.states.get(triggeredEntity)
newStatus = newState.state

erik = hass.states.get('device_tracker.erik')
sussa = hass.states.get('device_tracker.sussa')


if metatrackerName == 'device_tracker.erik':
    picture = '/local/erik.png'
elif metatrackerName == 'device_tracker.sussa':
    picture = '/local/sussa.jpg'

hass.states.set(metatrackerName, newStatus, {
    'friendly_name' : data.get('meta_entity'),
    'entity_picture' : picture
})
