'use client'

import { useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/stores/authStore'
import { 
  Sparkles, 
  Zap, 
  Shield, 
  Bell, 
  TrendingUp, 
  Globe, 
  Clock,
  CheckCircle2,
  ArrowRight,
  Brain,
  Target,
  DollarSign,
  Activity
} from 'lucide-react'

export default function LandingPage() {
  const router = useRouter()
  const { isAuthenticated, isHydrated } = useAuthStore()

  // Redirect authenticated users to dashboard
  useEffect(() => {
    if (isHydrated && isAuthenticated) {
      router.push('/dashboard')
    }
  }, [isAuthenticated, isHydrated, router])

  if (!isHydrated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  if (isAuthenticated) {
    return null // Will redirect
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
      {/* Navigation */}
      <nav className="container mx-auto px-6 py-6 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Sparkles className="h-8 w-8 text-blue-600" />
          <span className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
            Crypto AI Agent
          </span>
        </div>
        <div className="flex items-center space-x-4">
          <Link href="/login">
            <Button variant="ghost">Login</Button>
          </Link>
          <Link href="/register">
            <Button className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white px-8">
              Get Started Free
            </Button>
          </Link>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="container mx-auto px-6 py-20 text-center">
        <div className="max-w-4xl mx-auto">
          <div className="inline-flex items-center space-x-2 bg-blue-100 text-blue-700 px-4 py-2 rounded-full text-sm font-medium mb-6">
            <Brain className="h-4 w-4" />
            <span>Powered by Advanced AI Technology</span>
          </div>
          
          <h1 className="text-6xl md:text-7xl font-extrabold mb-6 bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent leading-tight">
            Never Miss a Crypto Opportunity Again
          </h1>
          
          <p className="text-xl md:text-2xl text-gray-700 mb-8 leading-relaxed max-w-3xl mx-auto">
            Unify all your crypto portfolios from <span className="font-semibold text-blue-600">Binance</span>, <span className="font-semibold text-purple-600">Bitfinex</span>, and more in one powerful dashboard. 
            <span className="font-semibold text-purple-600"> AI-powered recommendations</span> and <span className="font-semibold text-green-600">real-time price alerts</span> ensure you never miss a significant movement.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-12">
            <Link href="/register">
              <Button 
                size="lg" 
                className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white text-lg px-10 py-6 h-auto shadow-xl hover:shadow-2xl transform hover:scale-105 transition-all duration-200"
              >
                Start Managing Your Portfolio Now
                <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
            </Link>
          </div>

          <div className="flex items-center justify-center space-x-8 text-sm text-gray-600">
            <div className="flex items-center space-x-2">
              <CheckCircle2 className="h-5 w-5 text-green-500" />
              <span>Free Forever</span>
            </div>
            <div className="flex items-center space-x-2">
              <CheckCircle2 className="h-5 w-5 text-green-500" />
              <span>No Credit Card</span>
            </div>
            <div className="flex items-center space-x-2">
              <CheckCircle2 className="h-5 w-5 text-green-500" />
              <span>Setup in 60 Seconds</span>
            </div>
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="container mx-auto px-6 py-20">
        <div className="text-center mb-16">
          <h2 className="text-4xl md:text-5xl font-bold mb-4 text-gray-900">
            Everything You Need to <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">Maximize Your Crypto Earnings</span>
          </h2>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Advanced AI technology meets precision portfolio management. Nothing gets left behind.
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8 max-w-7xl mx-auto">
          {/* Feature 1: AI Recommendations */}
          <div className="bg-white p-8 rounded-2xl shadow-lg hover:shadow-xl transition-shadow border border-gray-100">
            <div className="bg-gradient-to-br from-blue-500 to-purple-500 w-14 h-14 rounded-xl flex items-center justify-center mb-6">
              <Brain className="h-7 w-7 text-white" />
            </div>
            <h3 className="text-2xl font-bold mb-3 text-gray-900">AI-Powered Recommendations</h3>
            <p className="text-gray-600 leading-relaxed">
              Our advanced AI analyzes market trends, your portfolio performance, and historical data to provide personalized recommendations. Make smarter decisions with insights powered by machine learning.
            </p>
          </div>

          {/* Feature 2: Multi-Platform */}
          <div className="bg-white p-8 rounded-2xl shadow-lg hover:shadow-xl transition-shadow border border-gray-100">
            <div className="bg-gradient-to-br from-orange-500 to-pink-500 w-14 h-14 rounded-xl flex items-center justify-center mb-6">
              <Globe className="h-7 w-7 text-white" />
            </div>
            <h3 className="text-2xl font-bold mb-3 text-gray-900">One Unified Dashboard</h3>
            <p className="text-gray-600 leading-relaxed">
              Import from Binance, Bitfinex, CSV files, or add manually. All your crypto assets from different platforms in one place. Stop switching between exchanges - see everything at a glance.
            </p>
          </div>

          {/* Feature 3: Real-Time Alerts */}
          <div className="bg-white p-8 rounded-2xl shadow-lg hover:shadow-xl transition-shadow border border-gray-100">
            <div className="bg-gradient-to-br from-green-500 to-emerald-500 w-14 h-14 rounded-xl flex items-center justify-center mb-6">
              <Bell className="h-7 w-7 text-white" />
            </div>
            <h3 className="text-2xl font-bold mb-3 text-gray-900">Never Miss a Move</h3>
            <p className="text-gray-600 leading-relaxed">
              Get instant Telegram notifications when prices hit your targets. Set alerts for above/below thresholds. Our robust recovery system ensures you never miss an alert, even during downtime.
            </p>
          </div>

          {/* Feature 4: Precision Management */}
          <div className="bg-white p-8 rounded-2xl shadow-lg hover:shadow-xl transition-shadow border border-gray-100">
            <div className="bg-gradient-to-br from-purple-500 to-indigo-500 w-14 h-14 rounded-xl flex items-center justify-center mb-6">
              <Target className="h-7 w-7 text-white" />
            </div>
            <h3 className="text-2xl font-bold mb-3 text-gray-900">Precise & Time-Sensitive</h3>
            <p className="text-gray-600 leading-relaxed">
              Track purchase dates, weighted average prices, commissions, and source platforms. Every transaction is recorded with precision. Historical tracking ensures accurate P&L calculations.
            </p>
          </div>

          {/* Feature 5: Multi-Currency */}
          <div className="bg-white p-8 rounded-2xl shadow-lg hover:shadow-xl transition-shadow border border-gray-100">
            <div className="bg-gradient-to-br from-yellow-500 to-orange-500 w-14 h-14 rounded-xl flex items-center justify-center mb-6">
              <DollarSign className="h-7 w-7 text-white" />
            </div>
            <h3 className="text-2xl font-bold mb-3 text-gray-900">Multi-Currency Support</h3>
            <p className="text-gray-600 leading-relaxed">
              Track your portfolio in USD, EUR, CZK, or any currency. Real-time conversion rates with 30-minute caching. See your true performance regardless of your base currency.
            </p>
          </div>

          {/* Feature 6: Real-Time Analytics */}
          <div className="bg-white p-8 rounded-2xl shadow-lg hover:shadow-xl transition-shadow border border-gray-100">
            <div className="bg-gradient-to-br from-cyan-500 to-blue-500 w-14 h-14 rounded-xl flex items-center justify-center mb-6">
              <Activity className="h-7 w-7 text-white" />
            </div>
            <h3 className="text-2xl font-bold mb-3 text-gray-900">Live Performance Tracking</h3>
            <p className="text-gray-600 leading-relaxed">
              WebSocket-powered real-time price updates. See your portfolio value change live. P&L calculations update instantly. Make decisions based on current market conditions, not stale data.
            </p>
          </div>
        </div>
      </section>

      {/* Technology Section */}
      <section className="bg-gradient-to-r from-blue-600 to-purple-600 py-20">
        <div className="container mx-auto px-6">
          <div className="max-w-4xl mx-auto text-center text-white">
            <Zap className="h-16 w-16 mx-auto mb-6" />
            <h2 className="text-4xl md:text-5xl font-bold mb-6">
              Built with Cutting-Edge Technology
            </h2>
            <p className="text-xl mb-8 opacity-90 leading-relaxed">
              FastAPI backend, Next.js frontend, PostgreSQL database, Redis caching, and WebSocket real-time updates. 
              Enterprise-grade architecture ensures reliability, speed, and scalability.
            </p>
            <div className="grid md:grid-cols-3 gap-8 mt-12">
              <div className="bg-white/10 backdrop-blur-sm rounded-xl p-6 border border-white/20">
                <Clock className="h-8 w-8 mx-auto mb-4" />
                <h3 className="font-bold text-lg mb-2">Lightning Fast</h3>
                <p className="text-sm opacity-90">Sub-second response times. 10x faster than traditional solutions.</p>
              </div>
              <div className="bg-white/10 backdrop-blur-sm rounded-xl p-6 border border-white/20">
                <Shield className="h-8 w-8 mx-auto mb-4" />
                <h3 className="font-bold text-lg mb-2">Bank-Level Security</h3>
                <p className="text-sm opacity-90">JWT authentication, encrypted credentials, read-only API access.</p>
              </div>
              <div className="bg-white/10 backdrop-blur-sm rounded-xl p-6 border border-white/20">
                <TrendingUp className="h-8 w-8 mx-auto mb-4" />
                <h3 className="font-bold text-lg mb-2">Always Available</h3>
                <p className="text-sm opacity-90">Robust recovery systems. Never miss an alert, even during downtime.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="container mx-auto px-6 py-20">
        <div className="max-w-4xl mx-auto bg-gradient-to-r from-blue-600 to-purple-600 rounded-3xl p-12 text-center text-white shadow-2xl">
          <h2 className="text-4xl md:text-5xl font-bold mb-6">
            Ready to Transform Your Crypto Portfolio Management?
          </h2>
          <p className="text-xl mb-8 opacity-90">
            Join thousands of traders who never miss an opportunity. Start managing all your crypto assets from one powerful dashboard today.
          </p>
          <Link href="/register">
            <Button 
              size="lg" 
              className="bg-white text-blue-600 hover:bg-gray-100 text-lg px-12 py-6 h-auto shadow-xl hover:shadow-2xl transform hover:scale-105 transition-all duration-200 font-bold"
            >
              Register Now - It's Free Forever
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
          </Link>
          <p className="mt-6 text-sm opacity-75">
            No credit card required • Setup in 60 seconds • Cancel anytime
          </p>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-gray-400 py-12">
        <div className="container mx-auto px-6">
          <div className="grid md:grid-cols-3 gap-8">
            <div>
              <div className="flex items-center space-x-2 mb-4">
                <Sparkles className="h-6 w-6 text-blue-400" />
                <span className="text-xl font-bold text-white">Crypto AI Agent</span>
              </div>
              <p className="text-sm">
                The ultimate cryptocurrency portfolio management platform powered by AI.
              </p>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Features</h4>
              <ul className="space-y-2 text-sm">
                <li>AI Recommendations</li>
                <li>Multi-Platform Import</li>
                <li>Price Alerts</li>
                <li>Real-Time Tracking</li>
              </ul>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Get Started</h4>
              <ul className="space-y-2 text-sm">
                <li>
                  <Link href="/register" className="hover:text-white transition-colors">
                    Create Free Account
                  </Link>
                </li>
                <li>
                  <Link href="/login" className="hover:text-white transition-colors">
                    Login
                  </Link>
                </li>
              </ul>
            </div>
          </div>
          <div className="border-t border-gray-800 mt-8 pt-8 text-center text-sm">
            <p>&copy; 2025 Crypto AI Agent. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  )
}

