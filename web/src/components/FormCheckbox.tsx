import React, { InputHTMLAttributes } from 'react';

interface FormCheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: string;
  error?: string;
}

const FormCheckbox: React.FC<FormCheckboxProps> = ({ label, error, className = '', ...props }) => {
  return (
    <div className="space-y-1">
      <label className="inline-flex items-center">
        <input
          type="checkbox"
          {...props}
          className={`
            w-4 h-4 text-blue-600 border-gray-300 rounded
            focus:ring-2 focus:ring-blue-500/20
            hover:border-blue-500 transition-colors duration-200
            ${error ? 'border-red-300' : ''}
            ${className}
          `}
        />
        <span className="ml-2 text-sm text-gray-700">{label}</span>
      </label>
      {error && (
        <p className="text-sm text-red-600">{error}</p>
      )}
    </div>
  );
};

export default FormCheckbox; 