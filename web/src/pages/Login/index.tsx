import LoginForm from "./components/login-form";

export default function LoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-white via-gray-50 to-slate-100">
      <div className="flex flex-col lg:flex-row bg-white rounded-2xl shadow-xl overflow-hidden max-w-5xl w-full h-[600px]">
        <div className="lg:w-7/12 relative">
          <img
            src="https://i.pinimg.com/736x/69/84/3e/69843e99dbfc7b273f8508aa23cf4f60.jpg"
            alt="Welcome Illustration"
            className="absolute inset-0 w-full h-full object-cover"
          />
          <div className="absolute inset-0 bg-black bg-opacity-10 flex items-center justify-center p-8">
            <div className="text-center text-white">
              <h2 className="text-3xl font-bold mb-2">AI Review Workspace</h2>
              <p className="text-lg opacity-90">Use GitHub OAuth to connect repositories, or sign in with an existing backend-issued account.</p>
            </div>
          </div>
        </div>

        <div className="lg:w-5/12 p-10 flex flex-col justify-center">
          <div className="flex items-start mb-8">
            <h2 className="text-2xl font-bold text-gray-800">Sign in</h2>
            <div className="ml-auto flex items-center text-blue-500 text-sm font-medium">
              <div className="w-2.5 h-2.5 rounded-full bg-blue-500 mr-1.5"></div>
              Automated Code Review
            </div>
          </div>

          <LoginForm />

          <div className="mt-6 text-sm text-gray-500 rounded-lg border border-blue-100 bg-blue-50 px-4 py-3">
            New users should start with GitHub OAuth. Direct email signup is not wired in the current backend yet.
          </div>
        </div>
      </div>
    </div>
  );
}
