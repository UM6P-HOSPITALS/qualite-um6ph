from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

# Les tâches planifiées réelles (rappels de révision à J-15, relances
# d'évaluation, détection de retards d'audit...) seront ajoutées ici au
# fur et à mesure des tickets FEATURE-DOC-10, FEATURE-EI-*, FEATURE-AUD-*.
#
# Exemple à venir :
# @scheduler.scheduled_job("cron", hour=6)
# def check_document_revisions():
#     ...


def start_scheduler():
    scheduler.start()
