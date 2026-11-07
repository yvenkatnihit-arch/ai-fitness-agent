// "lower_back" -> "lower back", "leg_press_machine" -> "leg press machine"
export const words = (value: string) => value.replaceAll('_', ' ')
