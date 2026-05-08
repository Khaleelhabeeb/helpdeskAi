import { 
  Zap, 
  Rocket, 
  ArrowRight, 
  Bot, 
  Database,
  CheckCircle2
} from 'lucide-react';
import { motion } from 'motion/react';
import { Link } from 'react-router-dom';
import { cn } from '../lib/utils';
import { Logo } from '../components/Logo';

export default function Landing() {
  return (
    <div className="min-h-screen bg-surface selection:bg-brand-primary selection:text-brand-on-primary">
      {/* Header */}
      <header className="w-full h-16 border-b border-surface-container-highest bg-surface/80 backdrop-blur-md flex items-center justify-between px-4 md:px-8 sticky top-0 z-50">
        <Logo />
        <nav className="hidden md:flex items-center gap-8">
          <a href="#features" className="text-sm font-medium text-on-surface-variant hover:text-brand-primary transition-colors">Features</a>
          <a href="#pricing" className="text-sm font-medium text-on-surface-variant hover:text-brand-primary transition-colors">Pricing</a>
          <a href="#docs" className="text-sm font-medium text-on-surface-variant hover:text-brand-primary transition-colors">Documentation</a>
        </nav>
        <div className="flex items-center gap-4">
          <Link to="/login" className="text-sm font-medium text-brand-primary hover:text-on-surface-variant transition-colors">Sign In</Link>
          <Link to="/login" className="bg-brand-primary text-brand-on-primary text-sm font-medium px-4 py-2 rounded-lg hover:opacity-90 transition-opacity">
            Get Started
          </Link>
        </div>
      </header>

      <main>
        {/* Hero Section */}
        <section className="max-w-7xl mx-auto px-8 py-24 md:py-32 flex flex-col items-center text-center">
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="inline-flex items-center gap-2 px-3 py-1 border border-surface-container-highest rounded-full bg-surface-container-lowest mb-8 animate-slam-in"
          >
            <Rocket className="w-4 h-4 text-brand-primary" />
            <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">v2.0 Now Available</span>
          </motion.div>
          
          <motion.h1 
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.1 }}
            className="text-5xl md:text-7xl font-bold text-brand-primary max-w-4xl mb-6 tracking-tighter leading-[1.05]"
          >
            HelpDeskAI: Autonomous Customer Care
          </motion.h1>
          
          <motion.p 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="text-lg md:text-xl text-on-surface-variant max-w-2xl mb-12"
          >
            Integrate precise, reliable AI agents with Slack, WhatsApp, and your website. Resolve tickets faster with uncompromising technical accuracy.
          </motion.p>
          
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="flex flex-col sm:flex-row items-center gap-4"
          >
            <Link to="/login" className="bg-brand-primary text-brand-on-primary font-medium h-12 px-8 rounded-lg hover:opacity-90 transition-all flex items-center gap-2 group">
              Get Started
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Link>
            <button className="bg-surface-container-lowest border border-surface-container-highest text-brand-primary font-medium h-12 px-8 rounded-lg hover:bg-surface-container-low transition-colors">
              View Documentation
            </button>
          </motion.div>

          {/* Hero Graphic */}
          <motion.div 
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="w-full max-w-5xl aspect-[16/9] mt-24 border border-surface-container-highest rounded-xl bg-surface-container-lowest shadow-2xl overflow-hidden relative flex flex-col group"
          >
            <div className="h-10 border-b border-surface-container-highest bg-surface-container-low flex items-center px-4 gap-2">
              <div className="w-3 h-3 rounded-full border border-surface-container-highest bg-red-400/20" />
              <div className="w-3 h-3 rounded-full border border-surface-container-highest bg-yellow-400/20" />
              <div className="w-3 h-3 rounded-full border border-surface-container-highest bg-green-400/20" />
            </div>
            <div className="flex-1 relative bg-[#09090b]">
              <img 
                src="/landing.png" 
                alt="Product Dashboard Visualization"
                className="w-full h-full object-cover opacity-60 grayscale group-hover:grayscale-0 transition-all duration-700"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-transparent to-transparent" />
              <div className="absolute bottom-8 left-8 text-left space-y-2">
                <div className="font-mono text-xs text-white/40">&gt; Initializing Autonomous Agent Cluster...</div>
                <div className="font-mono text-xs text-emerald-400">&gt; Connection established: Slack (Webhook connected)</div>
                <div className="font-mono text-xs text-emerald-400">&gt; Connection established: WhatsApp API (Active)</div>
                <div className="font-mono text-xs text-emerald-400">&gt; System ready. Awaiting inquiries.</div>
              </div>
            </div>
          </motion.div>
        </section>

        {/* Features Section */}
        <section id="features" className="max-w-7xl mx-auto px-8 py-24 md:py-32">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-brand-primary mb-4 tracking-tight">Engineered for Precision</h2>
            <p className="text-on-surface-variant max-w-xl mx-auto">
              A technical architecture designed to handle complex support workflows without human intervention.
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              { 
                icon: Bot, 
                title: 'Autonomous Support', 
                desc: 'Deploy intelligent agents capable of resolving multi-step technical inquiries using deterministic logic paths.',
                color: 'text-blue-500 bg-blue-50'
              },
              { 
                icon: Zap, 
                title: 'Multi-platform', 
                desc: 'A single unified knowledge core connected seamlessly to Slack, WhatsApp, email, and live website chat widgets.',
                color: 'text-amber-500 bg-amber-50'
              },
              { 
                icon: Database, 
                title: 'Knowledge Base', 
                desc: 'Ingest thousands of technical documents, API references, and past tickets. The system strictly citations its sources.',
                color: 'text-emerald-500 bg-emerald-50'
              }
            ].map((feature, i) => (
              <motion.div 
                key={i}
                whileHover={{ y: -5 }}
                className="border border-surface-container-highest bg-surface-container-lowest p-8 rounded-xl flex flex-col items-start group hover:border-brand-primary transition-colors"
              >
                <div className={cn(
                  "w-12 h-12 rounded-lg flex items-center justify-center mb-6 border border-surface-container-highest group-hover:bg-brand-primary group-hover:text-brand-on-primary transition-colors",
                  feature.color
                )}>
                  <feature.icon className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-bold text-brand-primary mb-3">{feature.title}</h3>
                <p className="text-sm text-on-surface-variant leading-relaxed">
                  {feature.desc}
                </p>
              </motion.div>
            ))}
          </div>
        </section>

        {/* CTA Section */}
        <section className="border-t border-surface-container-highest bg-surface py-24 px-8 text-center">
          <h2 className="text-3xl font-bold text-brand-primary mb-4">Ready to automate your technical support?</h2>
          <p className="text-on-surface-variant mb-10 max-w-xl mx-auto">Join forward-thinking engineering teams managing thousands of inquiries.</p>
          <Link to="/login" className="bg-brand-primary text-brand-on-primary font-medium h-12 px-8 rounded-lg hover:opacity-90 transition-opacity inline-flex items-center">
            Start Free Trial
          </Link>
        </section>
      </main>

      {/* Footer */}
      <footer className="max-w-7xl mx-auto px-8 py-12 flex flex-col md:flex-row items-center justify-between border-t border-surface-container-highest text-sm text-on-surface-variant">
        <div className="flex items-center gap-3 mb-6 md:mb-0">
          <Logo />
          <span className="ml-2 font-medium">© 2024 HelpDeskAI Inc.</span>
        </div>
        <div className="flex items-center gap-8">
          <a href="#" className="hover:text-brand-primary transition-colors">Terms</a>
          <a href="#" className="hover:text-brand-primary transition-colors">Privacy</a>
          <a href="#" className="hover:text-brand-primary transition-colors">Security</a>
        </div>
      </footer>
    </div>
  );
}
