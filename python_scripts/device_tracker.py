# Get Data from Automation Trigger
triggeredEntity = data.get('entity_id')
metatrackerName = "device_tracker." + data.get('meta_entity')

# Get new state
newState = hass.states.get(triggeredEntity)
newStatus = newState.state

erik = hass.states.get('person.erik')
sussa = hass.states.get('person.sussa')


if metatrackerName == 'person.erik':
    picture = '/local/erik.png'
elif metatrackerName == 'person.sussa':
    picture = '/local/sussa.jpg'

hass.states.set(metatrackerName, newStatus, {
    'friendly_name' : data.get('meta_entity'),
    'entity_picture' : picture
})
