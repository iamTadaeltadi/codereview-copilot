import type React from "react"

interface FormCheckboxProps {
  id: string
  label: React.ReactNode
  required?: boolean
}

export default function FormCheckbox({ id, label, required = false }: FormCheckboxProps) {
  return (
    <div className="flex items-center space-x-3">
      <input
        type="checkbox"
        id={id}
        required={required}
        className="h-4 w-4 rounded border-gray-300 text-blue-500 
          focus:ring-blue-200 focus:ring-offset-0
          transition-colors duration-200
          cursor-pointer"
      />
      <label htmlFor={id} className="text-sm text-gray-600 hover:text-gray-900 transition-colors cursor-pointer">
        {label}
      </label>
    </div>
  )
}
