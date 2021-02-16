import React, { InputHTMLAttributes } from 'react';
import { IconType } from 'react-icons';

interface FormInputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  icon?: IconType;
  error?: string;
}

const FormInput: React.FC<FormInputProps> = ({ label, icon: Icon, error, className = '', id, name, ...props }) => {
  const inputId = id ?? name ?? label.toLowerCase().replace(/\s+/g, '-');

  return (
    <div className="space-y-1">
      <label htmlFor={inputId} className="block text-sm font-medium text-gray-700">
        {label}
      </label>
      <div className="relative rounded-lg shadow-sm">
        {Icon && (
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Icon className="h-5 w-5 text-gray-400" />
          </div>
        )}
        <input
          {...props}
          id={inputId}
          name={name}
          className={`
            block w-full rounded-lg border-gray-200 
            ${Icon ? 'pl-10' : 'pl-4'} pr-4 py-2.5
            focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500
            disabled:bg-gray-50 disabled:text-gray-500
            transition-colors duration-200
            ${error ? 'border-red-300 focus:border-red-500 focus:ring-red-500/20' : ''}
            ${className}
          `}
        />
      </div>
      {error && (
        <p className="text-sm text-red-600 mt-1">{error}</p>
      )}
    </div>
  );
};

export default FormInput; 