import React from 'react';
import { FiAlertCircle } from 'react-icons/fi';

interface ErrorMessageProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  className?: string;
}

const ErrorMessage: React.FC<ErrorMessageProps> = ({
  title = 'Error',
  message,
  onRetry,
  className = ''
}) => {
  return (
    <div className={`flex items-center justify-center ${className}`}>
      <div className="max-w-md w-full bg-white p-8 rounded-xl shadow-sm border border-red-200">
        <div className="flex items-center justify-center w-12 h-12 mx-auto bg-red-100 rounded-full">
          <FiAlertCircle className="w-6 h-6 text-red-600" />
        </div>
        <h3 className="mt-4 text-lg font-medium text-center text-gray-900">{title}</h3>
        <p className="mt-2 text-sm text-center text-gray-500">{message}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-4 w-full px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-colors duration-200"
          >
            Try Again
          </button>
        )}
      </div>
    </div>
  );
};

export default ErrorMessage; 