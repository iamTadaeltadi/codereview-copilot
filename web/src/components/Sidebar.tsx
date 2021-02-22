// src/components/Sidebar.tsx
import React from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useDispatch } from "react-redux";
import { logout } from "../redux/slices/AuthSlice";
import { FiMenu, FiX, FiHome, FiClipboard, FiList, FiLogOut } from "react-icons/fi";
import { useSidebar } from "../contexts/SidebarContext";

const Sidebar: React.FC = () => {
  const { isOpen, setIsOpen } = useSidebar();
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    dispatch(logout());
    navigate('/');
  };

  const isActiveRoute = (path: string) => {
    return location.pathname === path;
  };

  return (
    <div
      className={`h-screen ${
        isOpen ? "w-64" : "w-20"
      } bg-slate-800 shadow-xl transition-all duration-300 fixed left-0 top-0 flex flex-col border-r border-slate-700 z-10`}
    >
      <div className="flex items-center justify-between p-4 border-b border-slate-700">
        {isOpen && (
          <span className="text-blue-400 font-semibold text-lg">Code Review AI</span>
        )}
        <button 
          className="p-2 hover:bg-slate-700 rounded-lg transition-colors duration-200" 
          onClick={() => setIsOpen(!isOpen)}
        >
          {isOpen ? <FiX size={24} className="text-slate-300" /> : <FiMenu size={24} className="text-slate-300" />}
      </button>
      </div>

      <nav className="flex-1 overflow-y-auto">
        <ul className="space-y-2 p-4">
          <li>
            <Link 
              to="/dashboard" 
              className={`flex items-center ${!isOpen ? 'justify-center' : 'space-x-3'} p-3 rounded-lg transition-all duration-200 ${
                isActiveRoute('/dashboard') 
                  ? 'bg-blue-600 text-white' 
                  : 'text-slate-300 hover:bg-slate-700'
